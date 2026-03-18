'use client';
import { useState, useEffect, useCallback } from 'react';

export default function AdminDashboard() {
  const [password, setPassword] = useState('');
  const [authed, setAuthed] = useState(false);
  const [storedPw, setStoredPw] = useState('');
  const [intakes, setIntakes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem('vi_admin_pw');
    if (saved) { setStoredPw(saved); setPassword(saved); setAuthed(true); }
  }, []);

  const fetchIntakes = useCallback(async (pw) => {
    setLoading(true); setError('');
    try {
      const params = new URLSearchParams({ limit: '100' });
      if (filterType) params.set('type', filterType);
      if (filterStatus) params.set('status', filterStatus);
      const res = await fetch('/api/admin/intakes?' + params, { headers: { Authorization: 'Bearer ' + pw } });
      if (res.status === 401) { setAuthed(false); setError('Wrong password'); return; }
      const data = await res.json();
      setIntakes(data.intakes || []);
    } catch (e) { setError('Failed: ' + e.message); }
    finally { setLoading(false); }
  }, [filterType, filterStatus]);

  useEffect(() => { if (authed && storedPw) fetchIntakes(storedPw); }, [authed, storedPw, fetchIntakes]);

  function handleLogin(e) {
    e.preventDefault();
    localStorage.setItem('vi_admin_pw', password);
    setStoredPw(password); setAuthed(true);
  }
  function handleLogout() {
    localStorage.removeItem('vi_admin_pw');
    setAuthed(false); setStoredPw(''); setPassword(''); setIntakes([]);
  }

  const filtered = intakes.filter(i => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (i.full_name||'').toLowerCase().includes(q)||(i.chief_complaint||'').toLowerCase().includes(q)||(i.caller_phone||'').includes(q);
  });

  const stats = {
    total: intakes.length,
    complete: intakes.filter(i=>i.completion_status==='complete').length,
    partial: intakes.filter(i=>i.completion_status==='partial').length,
    newP: intakes.filter(i=>i.visit_type==='new_patient').length,
    fu: intakes.filter(i=>i.visit_type==='follow_up').length,
  };

  if (!authed) return (
    <div style={{minHeight:'100vh',background:'#0f172a',display:'flex',alignItems:'center',justifyContent:'center',fontFamily:'system-ui,sans-serif'}}>
      <div style={{background:'#1e293b',borderRadius:16,padding:40,width:360,boxShadow:'0 25px 50px rgba(0,0,0,0.5)'}}>
        <div style={{textAlign:'center',marginBottom:32}}>
          <div style={{fontSize:40,marginBottom:8}}>🏥</div>
          <h1 style={{color:'white',margin:0,fontSize:22}}>VoiceIntake Admin</h1>
          <p style={{color:'#94a3b8',margin:'4px 0 0',fontSize:14}}>Global Neuro and Spine Institute</p>
        </div>
        <form onSubmit={handleLogin}>
          <label style={{color:'#94a3b8',fontSize:13,display:'block',marginBottom:6}}>PASSWORD</label>
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Admin password"
            style={{width:'100%',padding:'12px 14px',borderRadius:8,border:'1px solid #334155',background:'#0f172a',color:'white',fontSize:15,boxSizing:'border-box'}} autoFocus />
          {error && <p style={{color:'#f87171',fontSize:13,margin:'8px 0 0'}}>{error}</p>}
          <button type="submit" style={{width:'100%',marginTop:16,padding:13,borderRadius:8,background:'#3b82f6',color:'white',border:'none',fontSize:15,fontWeight:700,cursor:'pointer'}}>Sign In</button>
        </form>
      </div>
    </div>
  );

  return (
    <div style={{minHeight:'100vh',background:'#0f172a',color:'white',fontFamily:'system-ui,sans-serif'}}>
      <div style={{background:'#1e293b',borderBottom:'1px solid #334155',padding:'16px 32px',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
        <div style={{display:'flex',alignItems:'center',gap:12}}>
          <span style={{fontSize:24}}>🏥</span>
          <div>
            <h1 style={{margin:0,fontSize:18,fontWeight:700}}>VoiceIntake Admin</h1>
            <p style={{margin:0,fontSize:12,color:'#64748b'}}>Global Neuro and Spine Institute</p>
          </div>
        </div>
        <div style={{display:'flex',gap:12}}>
          <button onClick={()=>fetchIntakes(storedPw)} style={{padding:'8px 16px',borderRadius:8,background:'#334155',color:'#94a3b8',border:'none',cursor:'pointer',fontSize:13}}>Refresh</button>
          <button onClick={handleLogout} style={{padding:'8px 16px',borderRadius:8,background:'#334155',color:'#94a3b8',border:'none',cursor:'pointer',fontSize:13}}>Sign Out</button>
        </div>
      </div>
      <div style={{padding:32}}>
        <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:16,marginBottom:32}}>
          {[['Total',stats.total,'#3b82f6'],['Complete',stats.complete,'#22c55e'],['Partial',stats.partial,'#f59e0b'],['New Patients',stats.newP,'#8b5cf6'],['Follow-Ups',stats.fu,'#06b6d4']].map(([label,val,color])=>(
            <div key={label} style={{background:'#1e293b',borderRadius:12,padding:20,border:'1px solid #334155'}}>
              <div style={{fontSize:28,fontWeight:700,color}}>{val}</div>
              <div style={{fontSize:13,color:'#64748b',marginTop:2}}>{label}</div>
            </div>
          ))}
        </div>
        <div style={{display:'flex',gap:12,marginBottom:20,flexWrap:'wrap'}}>
          <input type="text" placeholder="Search name, complaint, phone..." value={search} onChange={e=>setSearch(e.target.value)}
            style={{flex:1,minWidth:240,padding:'10px 14px',borderRadius:8,border:'1px solid #334155',background:'#1e293b',color:'white',fontSize:14}} />
          <select value={filterType} onChange={e=>setFilterType(e.target.value)} style={{padding:'10px 14px',borderRadius:8,border:'1px solid #334155',background:'#1e293b',color:'white',fontSize:14}}>
            <option value="">All Visit Types</option>
            <option value="new_patient">New Patients</option>
            <option value="follow_up">Follow-Ups</option>
          </select>
          <select value={filterStatus} onChange={e=>setFilterStatus(e.target.value)} style={{padding:'10px 14px',borderRadius:8,border:'1px solid #334155',background:'#1e293b',color:'white',fontSize:14}}>
            <option value="">All Statuses</option>
            <option value="complete">Complete</option>
            <option value="partial">Partial</option>
          </select>
        </div>
        <div style={{display:'grid',gridTemplateColumns:selected?'1fr 400px':'1fr',gap:24}}>
          <div>
            {loading && <div style={{color:'#64748b',padding:40,textAlign:'center'}}>Loading...</div>}
            {!loading&&filtered.length===0&&<div style={{color:'#64748b',padding:60,textAlign:'center',background:'#1e293b',borderRadius:12}}>No intakes yet. Completed calls will appear here.</div>}
            {filtered.map(i=>(
              <div key={i.call_id} onClick={()=>setSelected(selected?.call_id===i.call_id?null:i)}
                style={{background:selected?.call_id===i.call_id?'#1e3a5f':'#1e293b',border:'1px solid '+(selected?.call_id===i.call_id?'#3b82f6':'#334155'),borderRadius:10,padding:'16px 20px',cursor:'pointer',marginBottom:8,display:'flex',alignItems:'center',gap:16}}>
                <div style={{flex:1}}>
                  <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
                    <span style={{fontWeight:700,fontSize:15}}>{i.full_name||'Unknown Patient'}</span>
                    <span style={{fontSize:11,padding:'2px 8px',borderRadius:20,background:i.visit_type==='new_patient'?'#1e1b4b':'#082f49',color:i.visit_type==='new_patient'?'#a78bfa':'#38bdf8',fontWeight:600}}>{i.visit_type==='new_patient'?'NEW':'FOLLOW-UP'}</span>
                    <span style={{fontSize:11,padding:'2px 8px',borderRadius:20,background:i.completion_status==='complete'?'#052e16':'#422006',color:i.completion_status==='complete'?'#4ade80':'#fb923c',fontWeight:600}}>{i.completion_status==='complete'?'Complete':'Partial'}</span>
                  </div>
                  <div style={{color:'#94a3b8',fontSize:13,marginTop:4}}>{i.chief_complaint||'No complaint'}{i.pain_severity?' - Pain: '+i.pain_severity+'/10':''}</div>
                  <div style={{color:'#475569',fontSize:12,marginTop:2}}>{i.completed_at?new Date(i.completed_at).toLocaleString():''}{i.caller_phone?' - '+i.caller_phone:''}</div>
                </div>
                <div style={{color:'#475569',fontSize:20}}>{'>'}</div>
              </div>
            ))}
          </div>
          {selected&&(
            <div style={{background:'#1e293b',border:'1px solid #334155',borderRadius:12,overflow:'hidden',position:'sticky',top:32,maxHeight:'calc(100vh - 100px)',overflowY:'auto'}}>
              <div style={{padding:'16px 20px',background:'#1e3a5f',display:'flex',justifyContent:'space-between',alignItems:'center',position:'sticky',top:0}}>
                <div>
                  <div style={{fontWeight:700,fontSize:16}}>{selected.full_name||'Unknown'}</div>
                  <div style={{fontSize:12,color:'#93c5fd'}}>{selected.visit_type==='new_patient'?'New Patient':'Follow-Up'}</div>
                </div>
                <button onClick={()=>setSelected(null)} style={{background:'none',border:'none',color:'#94a3b8',cursor:'pointer',fontSize:20}}>x</button>
              </div>
              <div style={{padding:20}}>
                {[['Chief Complaint',selected.chief_complaint],['Pain Location',selected.pain_location],['Severity',selected.pain_severity?selected.pain_severity+'/10':null],['Pain Description',selected.pain_description],['Worse When',selected.pain_worse],['Better When',selected.pain_better],['Medications',selected.medications],['Allergies',selected.allergies],['Conditions',selected.medical_conditions],['Surgeries',selected.surgeries],['Family Hx',selected.family_history],['Marital',selected.marital_status],['Employment',selected.employment],['Smoking',selected.smoking],['Alcohol',selected.alcohol],['Disability',selected.disability],['Review of Systems',selected.review_of_systems],['Pregnant',selected.pregnant],['Consent',selected.consent_given],['DOB',selected.dob],['Ht/Wt',[selected.height,selected.weight].filter(Boolean).join(' / ')||null],['Cause',selected.cause],['Phone',selected.caller_phone],['Call ID',selected.call_id],['Date',selected.completed_at?new Date(selected.completed_at).toLocaleString():null]].filter(([_,v])=>v&&v!=='null').map(([label,value])=>(
                  <div key={label} style={{marginBottom:14,paddingBottom:14,borderBottom:'1px solid #0f172a'}}>
                    <div style={{fontSize:11,color:'#64748b',fontWeight:600,textTransform:'uppercase',marginBottom:3}}>{label}</div>
                    <div style={{fontSize:14,color:'#e2e8f0',lineHeight:1.5}}>{value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
                                                                                                                                                                                                   }
