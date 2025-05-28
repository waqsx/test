import { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import './register_form.css';

export const RegisterForm = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await axios.post("http://localhost:5173/register", 
        { username, password },
        {
          headers: {
            "Content-Type": "application/json"
          }
        }
      );
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || "Registration failed");
      } else {
        setError("Registration failed. Please try again.");
      }
    }
  };

  return (
    <form className="register-form" onSubmit={handleSubmit}>
      {error && <p className="error-message">{error}</p>}
      {success && <p className="success-message">Registration successful! Redirecting to login...</p>}
      <div className="form-group">
        <label className="form-label">Username</label>
        <input
          className="form-input"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          placeholder="Choose a username"
        />
      </div>
      <div className="form-group">
        <label className="form-label">Password</label>
        <input
          className="form-input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          placeholder="Create a password"
        />
      </div>
      <button className="form-button" type="submit">Create Account</button>
    </form>
  );
};