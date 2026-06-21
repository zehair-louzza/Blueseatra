import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/Spinner';
import { toast } from 'sonner';
import { Plus, Loader2 } from 'lucide-react';

const ROLES = ['owner', 'admin', 'operator', 'viewer', 'billing_admin'];

export default function Members() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'operator' });
  const [busy, setBusy] = useState(false);
  const canManage = ['owner', 'admin'].includes(tenant?.role);

  const load = () => api.get('/members').then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await api.post('/members', form); toast.success(t('members.add')); setOpen(false); setForm({ name: '', email: '', password: '', role: 'operator' }); load(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  const changeRole = async (uid, role) => { await api.patch(`/members/${uid}`, { role }); toast.success('OK'); load(); };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-semibold tracking-tight">{t('members.title')}</h1>
        {canManage && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button className="gap-2" data-testid="add-member-button"><Plus className="h-4 w-4" />{t('members.invite')}</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>{t('members.invite')}</DialogTitle></DialogHeader>
              <form onSubmit={add} className="space-y-3">
                <div className="space-y-1.5"><Label>{t('members.name')}</Label><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="member-name-input" /></div>
                <div className="space-y-1.5"><Label>{t('members.email')}</Label><Input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="member-email-input" /></div>
                <div className="space-y-1.5"><Label>{t('members.password')}</Label><Input type="text" required minLength={6} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="member-password-input" /></div>
                <div className="space-y-1.5"><Label>{t('members.role')}</Label>
                  <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                    <SelectTrigger data-testid="member-role-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <DialogFooter><Button type="submit" className="w-full" disabled={busy} data-testid="submit-member-button">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{t('members.add')}</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        )}
      </div>
      <div className="mt-5">
        {!rows ? <Spinner /> : (
          <Card className="card-shadow overflow-hidden border-0">
            <Table data-testid="members-table">
              <TableHeader><TableRow><TableHead>{t('members.name')}</TableHead><TableHead>{t('members.email')}</TableHead><TableHead>{t('members.role')}</TableHead></TableRow></TableHeader>
              <TableBody>
                {rows.map((m) => (
                  <TableRow key={m.user_id}>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell className="text-muted-foreground">{m.email}</TableCell>
                    <TableCell>
                      {canManage ? (
                        <Select value={m.role} onValueChange={(v) => changeRole(m.user_id, v)}>
                          <SelectTrigger className="h-8 w-40" data-testid="member-role-change"><SelectValue /></SelectTrigger>
                          <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                        </Select>
                      ) : <span className="text-sm">{m.role}</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}
