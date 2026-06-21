import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    const token = localStorage.getItem('bs_token');
    if (!token) { setLoading(false); return; }
    try {
      const { data } = await api.get('/auth/me');
      setUser(data.user); setTenant(data.tenant); setTenants(data.tenants);
    } catch (e) {
      localStorage.removeItem('bs_token');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadMe(); }, [loadMe]);

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password });
    localStorage.setItem('bs_token', data.token);
    setUser(data.user); setTenant(data.tenant);
    await loadMe();
    return data;
  };

  const signup = async (payload) => {
    const { data } = await api.post('/auth/signup', payload);
    localStorage.setItem('bs_token', data.token);
    setUser(data.user); setTenant(data.tenant);
    await loadMe();
    return data;
  };

  const switchTenant = async (tenantId) => {
    const { data } = await api.post(`/auth/switch-tenant/${tenantId}`);
    localStorage.setItem('bs_token', data.token);
    setTenant(data.tenant);
    await loadMe();
  };

  const logout = () => {
    localStorage.removeItem('bs_token');
    setUser(null); setTenant(null); setTenants([]);
    window.location.href = '/';
  };

  return (
    <AuthContext.Provider value={{ user, tenant, tenants, loading, login, signup, logout, switchTenant, reload: loadMe }}>
      {children}
    </AuthContext.Provider>
  );
};
