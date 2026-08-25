import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/Spinner';
import { toast } from 'sonner';
import { Plus, Loader2, Pencil, Trash2, Check, X } from 'lucide-react';

const ROLES = ['owner', 'admin', 'operator', 'viewer', 'billing_admin'];

export default function Members() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'operator' });
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [nameDraft, setNameDraft] = useState('');
  const canManage = ['owner', 'admin'].includes(tenant?.role);
  const { user } = useAuth();

  const load = () => api.get('/members').then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await api.post('/members', form); toast.success(t('members.add')); setOpen(false); setForm({ name: '', email: '', password: '', role: 'operator' }); load(); }
    catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };

  const changeRole = async (uid, role) => { await api.patch(`/members/${uid}`, { role }); toast.success('OK'); load(); };

  const startEditName = (m) => { setEditingId(m.user_id); setNameDraft(m.name); };
  const saveName = async (uid) => {
    try { await api.patch(`/members/${uid}`, { name: nameDraft }); toast.success(t('members.name_updated')); setEditingId(null); load(); }
    catch (err) { toast.error(apiError(err, 'Failed')); }
  };
  const removeMember = async (uid) => {
    try { await api.delete(`/members/${uid}`); toast.success(t('members.removed')); load(); }
    catch (err) { toast.error(apiError(err, 'Failed')); }
  };

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
              <TableHeader><TableRow><TableHead>{t('members.name')}</TableHead><TableHead>{t('members.email')}</TableHead><TableHead>{t('members.role')}</TableHead>{canManage && <TableHead>{t('members.actions')}</TableHead>}</TableRow></TableHeader>
              <TableBody>
                {rows.map((m) => (
                  <TableRow key={m.user_id} data-testid="member-row">
                    <TableCell className="font-medium">
                      {editingId === m.user_id ? (
                        <div className="flex items-center gap-1.5">
                          <Input
                            value={nameDraft}
                            onChange={(e) => setNameDraft(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') saveName(m.user_id); if (e.key === 'Escape') setEditingId(null); }}
                            className="h-7 w-40"
                            autoFocus
                            data-testid="member-name-input-edit"
                          />
                          <Button size="icon" variant="ghost" className="h-7 w-7 text-emerald-600 hover:text-emerald-700" onClick={() => saveName(m.user_id)} data-testid="member-name-save"><Check className="h-4 w-4" /></Button>
                          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingId(null)} data-testid="member-name-cancel"><X className="h-4 w-4" /></Button>
                        </div>
                      ) : m.name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{m.email}</TableCell>
                    <TableCell>
                      {canManage ? (
                        <Select value={m.role} onValueChange={(v) => changeRole(m.user_id, v)}>
                          <SelectTrigger className="h-8 w-40" data-testid="member-role-change"><SelectValue /></SelectTrigger>
                          <SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
                        </Select>
                      ) : <span className="text-sm">{m.role}</span>}
                    </TableCell>
                    {canManage && (
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {editingId !== m.user_id && (
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => startEditName(m)} data-testid="member-edit-button"><Pencil className="h-4 w-4" /></Button>
                          )}
                          {m.user_id !== user?.id && (
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" data-testid="member-delete-button"><Trash2 className="h-4 w-4" /></Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>{t('members.delete_title')}</AlertDialogTitle>
                                  <AlertDialogDescription>{m.name} — {t('members.delete_desc')}</AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel data-testid="member-delete-cancel">{t('common.cancel')}</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => removeMember(m.user_id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90" data-testid="member-delete-confirm">{t('members.delete')}</AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          )}
                        </div>
                      </TableCell>
                    )}
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
