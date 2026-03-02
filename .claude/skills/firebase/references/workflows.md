# Firebase Workflows Reference

## Contents
- Add User to Allowlist
- Deploy with New Firebase Credentials
- Local Dev Without Firebase
- Troubleshoot Token Verification
- Migrate from Email/Password to Google Sign-In

---

## Add User to Allowlist

**When:** A new user needs access to the application.

**Steps:**

1. **Update the allowlist JSON:**

```bash
# Edit the allowlist file
vim toolbox/backend/data/allowed_users.json
```

```json
{
  "allowed_users": [
    "james@tablerocktx.com",
    "newuser@tablerocktx.com"
  ]
}
```

2. **Verify locally:**

```bash
cd toolbox/backend
python3 -c "
import json
with open('data/allowed_users.json') as f:
    data = json.load(f)
    print('Allowed users:', data['allowed_users'])
"
```

3. **Test in development:**

```bash
make dev
# Have the new user sign in via frontend
# Backend logs should show: "User authenticated: newuser@tablerocktx.com"
```

4. **Deploy to production:**

```bash
git add toolbox/backend/data/allowed_users.json
git commit -m "Add newuser@tablerocktx.com to allowlist"
git push origin main
# GitHub Actions deploys automatically
```

**Validation:**
- [ ] User can sign in without 403 errors
- [ ] Backend logs show successful authentication
- [ ] User can access protected routes

---

## Deploy with New Firebase Credentials

**When:** Setting up a new Firebase project or rotating credentials.

**Steps:**

1. **Create Firebase project:**
   - Go to Firebase Console: https://console.firebase.google.com
   - Create new project or select existing
   - Enable Authentication → Google Sign-In provider

2. **Get frontend config:**
   - Project Settings → General → Your apps → Web app
   - Copy config object

3. **Update frontend `.env`:**

```bash
cd toolbox/frontend
cat > .env <<EOF
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
EOF
```

4. **Create service account for backend:**
   - Firebase Console → Project Settings → Service Accounts
   - Generate new private key
   - Download JSON file

5. **Set up Cloud Run secret:**

```bash
# Upload service account key to Secret Manager
gcloud secrets create firebase-service-account \
  --data-file=serviceAccountKey.json \
  --project=tablerockenergy

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding firebase-service-account \
  --member=serviceAccount:YOUR_SERVICE_ACCOUNT@tablerockenergy.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor \
  --project=tablerockenergy
```

6. **Update Cloud Run deployment:**

```yaml
# toolbox/.github/workflows/deploy.yml
# Add secret mount
- name: Deploy to Cloud Run
  run: |
    gcloud run deploy table-rock-tools \
      --source . \
      --project tablerockenergy \
      --region us-central1 \
      --allow-unauthenticated \
      --set-secrets=GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-service-account:latest
```

7. **Test deployment:**

```bash
git add .
git commit -m "Update Firebase credentials"
git push origin main
# Wait for GitHub Actions to complete
curl https://tools.tablerocktx.com/api/health
```

**Validation:**
- [ ] Frontend shows Google Sign-In button
- [ ] Backend can verify tokens
- [ ] Protected routes return 200 with valid token

---

## Local Dev Without Firebase

**When:** Developing locally without Firebase credentials (e.g., working on CSV processing that doesn't need auth).

**Steps:**

1. **Disable Firebase in config:**

```bash
cd toolbox/backend
cat > .env <<EOF
FIRESTORE_ENABLED=false
DATABASE_ENABLED=false
EOF
```

2. **Skip auth on test routes:**

```python
# toolbox/backend/app/api/extract.py
from app.core.config import settings

@router.post("/upload")
async def upload_pdf(
    file: UploadFile,
    user: dict = Depends(get_current_user) if settings.environment == "production" else None
):
    # Skip auth in local dev
    pass
```

**WARNING:** Never deploy with auth disabled. Use environment checks carefully.

3. **Use mock user for testing:**

```python
# toolbox/backend/app/core/auth.py
from app.core.config import settings

async def get_current_user(authorization: str = Header(None)) -> dict:
    if settings.environment == "development" and not authorization:
        # Return mock user for local dev
        return {"email": "dev@localhost", "uid": "dev-user"}
    
    # Normal auth flow
    # ...
```

4. **Run without credentials:**

```bash
make dev
# Backend starts without Firebase initialization
# Firestore operations fall back to in-memory or local storage
```

**Validation:**
- [ ] Backend starts without Firebase errors
- [ ] API endpoints work with mock user
- [ ] Storage operations use local filesystem

---

## Troubleshoot Token Verification

**When:** API returns 401 "Invalid token" errors.

**Debug checklist:**

1. **Check token format:**

```typescript
// Frontend console
const user = auth.currentUser;
const token = await user.getIdToken();
console.log('Token:', token);
console.log('Token parts:', token.split('.').length); // Should be 3 (JWT)
```

2. **Verify backend receives token:**

```python
# toolbox/backend/app/core/auth.py
async def get_current_user(authorization: str = Header(None)) -> dict:
    print(f"Authorization header: {authorization}")  # DEBUG
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing header")
    # ...
```

3. **Check Firebase Admin initialization:**

```python
# toolbox/backend/app/core/auth.py
def _init_firebase():
    global _firebase_initialized
    if not _firebase_initialized:
        try:
            from firebase_admin import credentials, initialize_app
            cred = credentials.ApplicationDefault()
            print(f"Using credentials: {cred.project_id}")  # DEBUG
            initialize_app(cred)
            _firebase_initialized = True
        except Exception as e:
            print(f"Firebase init failed: {e}")  # DEBUG
            raise
```

4. **Test token manually:**

```bash
# Get token from frontend console, then:
curl -X POST http://localhost:8000/api/extract/upload \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@test.pdf"
```

5. **Common issues:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing authorization header` | Frontend not sending token | Check `getAuthHeaders()` |
| `Invalid token: Token expired` | Token older than 1 hour | Call `getIdToken(true)` to force refresh |
| `GOOGLE_APPLICATION_CREDENTIALS not set` | Missing backend credentials | Run `gcloud auth application-default login` |
| `User not authorized` | Email not in allowlist | Add email to `allowed_users.json` |

**Iterate until pass:**
1. Make changes based on error
2. Restart backend: `make dev-backend`
3. Test with curl or frontend
4. If still failing, add more debug logs and repeat

---

## Migrate from Email/Password to Google Sign-In

**When:** Existing users with email/password auth need to switch to Google Sign-In.

**Steps:**

1. **Enable Google provider in Firebase Console:**
   - Authentication → Sign-in method → Google → Enable

2. **Update frontend UI to show Google Sign-In:**

```typescript
// toolbox/frontend/src/pages/Login.tsx
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { auth } from '../lib/firebase';

function Login() {
  async function handleGoogleSignIn() {
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(auth, provider);
      // Redirect to dashboard
    } catch (error) {
      console.error('Google sign-in failed:', error);
    }
  }

  return (
    <div>
      <button onClick={handleGoogleSignIn}>
        Sign in with Google
      </button>
      {/* Keep email/password form for legacy users */}
    </div>
  );
}
```

3. **Link existing accounts (optional):**

```typescript
import { linkWithPopup, GoogleAuthProvider } from 'firebase/auth';

async function linkGoogleAccount() {
  const user = auth.currentUser;
  if (!user) throw new Error('Not signed in');

  const provider = new GoogleAuthProvider();
  try {
    await linkWithPopup(user, provider);
    console.log('Google account linked');
  } catch (error) {
    console.error('Link failed:', error);
  }
}
```

4. **Notify users:**
   - Send email: "We're migrating to Google Sign-In for better security"
   - Add banner in app: "Please link your Google account"

5. **Deprecate email/password (after migration period):**
   - Firebase Console → Authentication → Sign-in method → Email/Password → Disable
   - Remove email/password form from frontend

**Validation:**
- [ ] Users can sign in with Google
- [ ] Existing user data is preserved (same UID)
- [ ] Backend allowlist still works (check by email)