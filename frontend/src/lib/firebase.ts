import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDGTk6hpc4dk2MPGCBoky_kegUrg7dUuYk",
  authDomain: "tablerockenergy.firebaseapp.com",
  projectId: "tablerockenergy",
  storageBucket: "tablerockenergy.firebasestorage.app",
  messagingSenderId: "781074525174",
  appId: "1:781074525174:web:f00b83c5401fe4b00d35d7",
  measurementId: "G-YZYXTHXBV9"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Auth
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

export default app;
