import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('bhoomi_user');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });
  const [token, setToken] = useState(() => localStorage.getItem('bhoomi_token'));
  const [loading, setLoading] = useState(false);

  const login = async (username, password) => {
    setLoading(true);
    try {
      const res = await api.post('/auth/login', { username, password });
      const { access_token, user: userData } = res.data;
      setToken(access_token);
      setUser(userData);
      localStorage.setItem('bhoomi_token', access_token);
      localStorage.setItem('bhoomi_user', JSON.stringify(userData));
      return { success: true, user: userData };
    } catch (err) {
      const errMsg = err.response?.data?.detail || 'Login failed. Please verify credentials.';
      return {
        success: false,
        error: errMsg
      };
    } finally {
      setLoading(false);
    }
  };

  // switchRole() previously carried a second copy of the demo password map in the
  // shipped bundle. Removed: changing role means signing in as that account.

  const logout = async () => {
    try {
      if (token) {
        await api.post('/auth/logout');
      }
    } catch (e) {
      // ignore logout network errors
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem('bhoomi_token');
      localStorage.removeItem('bhoomi_user');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        isAuthenticated: !!token && !!user
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
