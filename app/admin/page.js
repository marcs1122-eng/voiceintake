'use client';
import { useState, useEffect } from 'react';

export default function AdminDashboard() {
  const [intakes, setIntakes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [password, setPassword] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  async function login() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/intakes', {
        headers: { Authorization: `Bearer ${password}` },
      });
      if (res.status === 401) {
        setError('Incorrect password');
        setLoading(false);
        return;
      }
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setIntakes(data.intakes || []);
      setAuthenticated(true);
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  }

  function downloadPDF(intake) {
    window.open(`/api/admin/pdf/${intake.callSid}`, '_blank');
  }

  const filtered = intakes.filter(i => {
    const matchSearch =
      !search ||
      (i.patientName || '').toLowerCase().includes(search.toLowerCase()) ||
      (i.chiefComplaint || '').toLowerCase().includes(search.toLowerCase());
    const matchType =
      typeFilter === 'all' ||
      (i.visitType || 'new_patient') === typeFilter;
    return matchSearch && matchType;
  });

  const stats = {
    total: intakes.length,
    today: intakes.filter(i => {
      if (!i.completedAt) return false;
      const d = new Date(i.completedAt);
      const now = new Date();
      return d.toDateString() === now.toDateString();
    }).length,
    newPatients: intakes.filter(i => (i.visitType || 'new_patient') === 'new_patient').length,
    followUps: intakes.filter(i => i.visitType === 'follow_up').length,
  };

  if (!authenticated) {
    return (
      <div style={{ minHeight: '100vh', background: '#0f172a', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ background: '#1e293b', borderRadius: 12, padding: 40, width: 360, boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>🏥</div>
            <h1 style={{ color: '#f1f5f9', fontSize: 22, fontWeight: 700, margin: 0 }}>VoiceIntake Admin</h1>
            <p style={{ color: '#94a3b8', fontSize: 14, marginTop: 8 }}>Global Neuro &amp; Spine Institute</p>
          </div>
          {error && (
            <div style={{ background: '#450a0a', border: '1px solid #7f1d1d', borderRadius: 8, padding: 12, marginBottom: 16, color: '#fca5a5', fontSize: 14 }}>
              {error}
            </div>
          )}
          <input
            type="password"
            placeholder="Admin password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && login()}
            style={{ width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: 8, padding: '12px 16px', color: '#f1f5f9', fontSize: 15, boxSizing: 'border-box', outline: 'none', marginBottom: 16 }}
          />
          <button
            onClick={login}
            disabled={loading || !password}
            style={{ width: '100%', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 8, padding: '12px 0', fontSize: 15, fontWeight: 600, cursor: 'pointer' }}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', fontFamily: 'system-ui, sans-serif', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ background: '#1e293b', borderBottom: '1px solid #334155', padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24 }}>🏥</span>
          <div>
            <h1 style={{ color: '#f1f5f9', fontSize: 18, fontWeight: 700, margin: 0 }}>VoiceIntake Admin</h1>
            <p style={{ color: '#64748b', fontSize: 12, margin: 0 }}>Global Neuro &amp; Spine Institute</p>
          </div>
        </div>
        <button
          onClick={() => { setAuthenticated(false); setIntakes([]); setPassword(''); }}
          style={{ background: 'transparent', border: '1px solid #334155', color: '#94a3b8', borderRadius: 6, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}
        >
          Sign Out
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, padding: '20px 24px 0' }}>
        {[
          { label: 'Total Intakes', value: stats.total, color: '#3b82f6' },
          { label: 'Today', value: stats.today, color: '#10b981' },
          { label: 'New Patients', value: stats.newPatients, color: '#8b5cf6' },
          { label: 'Follow-Ups', value: stats.followUps, color: '#f59e0b' },
        ].map(s => (
          <div key={s.label} style={{ background: '#1e293b', borderRadius: 10, padding: 20, borderTop: `3px solid ${s.color}` }}>
            <div style={{ color: s.color, fontSize: 28, fontWeight: 700 }}>{s.value}</div>
            <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ padding: '16px 24px', display: 'flex', gap: 12 }}>
        <input
          type="text"
          placeholder="Search by name or complaint…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ flex: 1, background: '#1e293b', border: '1px solid #334155', borderRadius: 8, padding: '10px 14px', color: '#f1f5f9', fontSize: 14, outline: 'none' }}
        />
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, padding: '10px 14px', color: '#f1f5f9', fontSize: 14, outline: 'none' }}
        >
          <option value="all">All Types</option>
          <option value="new_patient">New Patient</option>
          <option value="follow_up">Follow-Up</option>
        </select>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', gap: 0, padding: '0 24px 24px', overflow: 'hidden' }}>
        {/* List */}
        <div style={{ flex: selected ? '0 0 420px' : '1', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingRight: selected ? 16 : 0 }}>
          {filtered.length === 0 && (
            <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>
              {intakes.length === 0 ? 'No intakes yet.' : 'No results match your search.'}
            </div>
          )}
          {filtered.map(i => (
            <div
              key={i.callSid}
              onClick={() => setSelected(selected?.callSid === i.callSid ? null : i)}
              style={{
                background: selected?.callSid === i.callSid ? '#1e3a5f' : '#1e293b',
                border: `1px solid ${selected?.callSid === i.callSid ? '#3b82f6' : '#334155'}`,
                borderRadius: 10,
                padding: 16,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 15 }}>{i.patientName || 'Unknown'}</div>
                  <div style={{ color: '#94a3b8', fontSize: 13, marginTop: 3 }}>{i.chiefComplaint || 'No chief complaint'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{
                    background: i.visitType === 'follow_up' ? '#422006' : '#1a1a4e',
                    color: i.visitType === 'follow_up' ? '#fb923c' : '#818cf8',
                    borderRadius: 4,
                    padding: '2px 8px',
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                  }}>
                    {i.visitType === 'follow_up' ? 'Follow-Up' : 'New'}
                  </span>
                  <div style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>
                    {i.completedAt ? new Date(i.completedAt).toLocaleString() : '—'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Detail Panel */}
        {selected && (
          <div style={{ flex: 1, background: '#1e293b', borderRadius: 12, border: '1px solid #334155', overflowY: 'auto', padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ color: '#f1f5f9', fontSize: 18, fontWeight: 700, margin: 0 }}>{selected.patientName}</h2>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => downloadPDF(selected)}
                  style={{ background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}
                >
                  📄 Download PDF
                </button>
                <button
                  onClick={() => setSelected(null)}
                  style={{ background: 'transparent', border: '1px solid #334155', color: '#94a3b8', borderRadius: 6, padding: '8px 14px', cursor: 'pointer', fontSize: 13 }}
                >
                  ✕
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {[
                { label: 'Visit Type', value: selected.visitType === 'follow_up' ? 'Follow-Up' : 'New Patient' },
                { label: 'Completed', value: selected.completedAt ? new Date(selected.completedAt).toLocaleString() : '—' },
                { label: 'Chief Complaint', value: selected.chiefComplaint || selected.intakeData?.chief_complaint || '—' },
                { label: 'Pain Location', value: selected.intakeData?.pain_location || '—' },
                { label: 'Pain Severity', value: selected.intakeData?.pain_severity || '—' },
                { label: 'Pain Description', value: selected.intakeData?.pain_description || '—' },
                { label: 'Cause of Pain', value: selected.intakeData?.cause || '—' },
                { label: 'Radiating', value: selected.intakeData?.pain_radiation || '—' },
                { label: 'Pain Worse', value: selected.intakeData?.pain_worse || '—' },
                { label: 'Pain Better', value: selected.intakeData?.pain_better || '—' },
                { label: 'Treatments Tried', value: selected.intakeData?.treatments || '—' },
                { label: 'Medications', value: selected.intakeData?.medications || '—' },
                { label: 'Allergies', value: selected.intakeData?.allergies || '—' },
                { label: 'Medical Conditions', value: selected.intakeData?.medical_conditions || '—' },
                { label: 'Prior Surgeries', value: selected.intakeData?.surgeries || '—' },
                { label: 'Hospitalizations', value: selected.intakeData?.hospitalizations || '—' },
                { label: 'Family History', value: selected.intakeData?.family_history || '—' },
                { label: 'Marital Status', value: selected.intakeData?.marital_status || '—' },
                { label: 'Employment', value: selected.intakeData?.employment || '—' },
                { label: 'Smoking', value: selected.intakeData?.smoking || '—' },
                { label: 'Alcohol', value: selected.intakeData?.alcohol || '—' },
                { label: 'Disability Claim', value: selected.intakeData?.disability || '—' },
                { label: 'Date of Birth', value: selected.intakeData?.dob || '—' },
                { label: 'Height / Weight', value: selected.intakeData?.height && selected.intakeData?.weight ? `${selected.intakeData.height} / ${selected.intakeData.weight}` : '—' },
              ].map(field => (
                <div key={field.label} style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                  <div style={{ color: '#64748b', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{field.label}</div>
                  <div style={{ color: '#e2e8f0', fontSize: 14, marginTop: 4 }}>{field.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
