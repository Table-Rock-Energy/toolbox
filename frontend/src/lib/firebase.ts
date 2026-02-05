import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyAkHoSHcl0ak96GQF3hwnU88uc1GyG7_ao",
  authDomain: "table-rock-tools.firebaseapp.com",
  projectId: "table-rock-tools",
  storageBucket: "table-rock-tools.firebasestorage.app",
  messagingSenderId: "956869048095",
  appId: "1:956869048095:web:08c2cf02fa0ecf1928a22a",
  measurementId: "G-4JL0HFNG9F"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Auth
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

export default app;
