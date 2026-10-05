import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  FolderOpen,
  Plus,
  FileText,
  Table2,
  FlaskConical,
  History,
  Settings,
  Upload,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Download,
  Sparkles,
  BookOpen,
  Trash2
} from 'lucide-react';
import './style.css';
const API = 'http://127.0.0.1:8000';
const call = async (p, o = {}) => {
  let r = await fetch(API + p, o);
  if (!r.ok) throw new Error(await r.text());
  return r.headers.get('content-type')?.includes('json') ? r.json() : r.text();
};
function Mark() {
  return (
    <div className="brand">
      <div className="press">
        <i />
        <b />
        <em />
        <span />
      </div>
      <div>
        <strong>Calvad</strong>
        <small>Evidence, distilled.</small>
      </div>
    </div>
  );
}
function Side({ page, setPage, project }) {
  let items = [
    ['projects', 'Projects', FolderOpen],
    ['documents', 'Documents', FileText],
    ['plan', 'Extraction plan', FlaskConical],
    ['evidence', 'Evidence table', Table2],
    ['synthesis', 'Synthesis', BookOpen],
    ['audit', 'Audit log', History],
  ];
  return (
    <aside>
      <Mark />
      <nav>
        {items.map(([k, l, I]) => (
          <button
            key={k}
            disabled={!project && k != 'projects'}
            className={page == k ? 'active' : ''}
            onClick={() => setPage(k)}
          >
            <I size={17} />
            {l}
          </button>
        ))}
      </nav>
      <div className="asidefoot">
        <Settings size={16} /> Local research workspace
        <div className="dotline">
          <i />
          Ollama-backed
        </div>
      </div>
    </aside>
  );
}
function App() {
  const [page, setPage] = useState('projects'),
    [projects, setProjects] = useState([]),
    [pid, setPid] = useState(null),
    [project, setProject] = useState(null),
    [err, setErr] = useState('');
  const refresh = () => call('/projects').then(setProjects);
    useEffect(() => {
    refresh();
    }, []);
  useEffect(() => {
    if (pid) call('/projects/' + pid).then(setProject);
  }, [pid, page]);
  const open = (id) => {
    setPid(id);
    setPage('documents');
  };
  return (
    <div className="app">
      <Side page={page} setPage={setPage} project={project} />
      <main>
        {err && (
          <div className="error" onClick={() => setErr('')}>
            {err}
          </div>
        )}
        {page === 'projects' ? (
          <Projects
            rows={projects}
            open={open}
            refresh={refresh}
            fail={setErr}
          />
        ) : (
          <Workspace
            page={page}
            setPage={setPage}
            project={project}
            pid={pid}
            reload={() => call('/projects/' + pid).then(setProject)}
            fail={setErr}
          />
        )}
      </main>
    </div>
  );
}
function Projects({rows,open,refresh,fail}){
 const[name,setName]=useState(''),[q,setQ]=useState('');

 async function create(){
  try{
   let x=await call('/projects',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name,question:q})
   });
   setName('');
   setQ('');
   await refresh();
   open(x.id);
  }catch(e){
   fail(e.message);
  }
 }

 async function removeProject(e,project){
  e.stopPropagation();

  const confirmed=window.confirm(
   `Delete "${project.name}"?\n\n`+
   `This will permanently delete the project, its uploaded PDFs, `+
   `extracted evidence, synthesis and audit history.\n\n`+
   `This cannot be undone.`
  );

  if(!confirmed)return;

  try{
   await call(`/projects/${project.id}`,{
    method:'DELETE'
   });

   await refresh();
  }catch(e){
   fail(e.message);
  }
 }

 return <>
  <header>
   <span className="eyebrow">RESEARCH WORKSPACE</span>
   <h1>Your research projects</h1>
   <p>Turn research papers into structured evidence you can inspect.</p>
  </header>

  <section className="split">
   <div className="card">
    <h2>Projects</h2>

    {rows.length
     ? rows.map(r=>
       <div className="projectrow" key={r.id}>
        <button
         className="project"
         onClick={()=>open(r.id)}
        >
         <div>
          <b>{r.name}</b>
          <small>
            {r.documents} papers · {r.validated} validated values
          </small>
         </div>

         <span className={'pill '+r.status}>
          {r.status}
         </span>

         <ChevronRight/>
        </button>

        <button
         className="deletebutton"
         title="Delete project"
         onClick={e=>removeProject(e,r)}
        >
         <Trash2 size={17}/>
        </button>
       </div>
      )
     : <div className="empty">
        No projects yet. Create the first one.
       </div>
    }
   </div>

   <div className="card">
    <h2>New project</h2>

    <label>
     Project name
     <input
      value={name}
      onChange={e=>setName(e.target.value)}
      placeholder="Exercise and depressive symptoms"
     />
    </label>

    <label>
     Research question
     <textarea
      value={q}
      onChange={e=>setQ(e.target.value)}
      placeholder="What is the effect of…?"
     />
    </label>

    <button
     className="primary"
     disabled={!name||!q}
     onClick={create}
    >
     <Plus size={17}/>
     Create project
    </button>
   </div>
  </section>
 </>
}
function Workspace({ page, setPage, project, pid, reload, fail }) {
  if (!project) return <div className="loading">Loading…</div>;
  let props = { project, pid, setPage, reload, fail };
  return (
    <>
      <header>
        <span className="eyebrow">{project.status.toUpperCase()}</span>
        <h1>{project.name}</h1>
        <p>{project.question}</p>
        <div className="meta">
          {project.documents.length} documents · {project.fields.length}{' '}
          extraction fields
        </div>
      </header>
      {page === 'documents' && <Documents {...props} />}{' '}
      {page === 'plan' && <Plan {...props} />}{' '}
      {page === 'evidence' && <Evidence {...props} />}{' '}
      {page === 'synthesis' && <Synthesis {...props} />}{' '}
      {page === 'audit' && <Audit {...props} />}
    </>
  );
}
function Documents({project,pid,setPage,reload,fail}){
 const[files,setFiles]=useState([]),
       [busy,setBusy]=useState(false);

 async function upload(){
  setBusy(true);

  try{
   let fd=new FormData();

   [...files].forEach(f=>fd.append('files',f));

   await call(`/projects/${pid}/documents`,{
    method:'POST',
    body:fd
   });

   await reload();
   setFiles([]);
  }catch(e){
   fail(e.message);
  }

  setBusy(false);
 }

 async function removeDocument(document){
  const confirmed=window.confirm(
   `Remove "${document.name}" from this project?\n\n`+
   `Evidence extracted from this document will also be removed. `+
   `Any existing synthesis will be invalidated.\n\n`+
   `This cannot be undone.`
  );

  if(!confirmed)return;

  try{
   await call(
    `/projects/${pid}/documents/${document.id}`,
    {method:'DELETE'}
   );

   await reload();
  }catch(e){
   fail(e.message);
  }
 }

 return <section className="card wide">

  <div className="sectionhead">
   <div>
    <h2>Add research documents</h2>
    <p>
     Text-based academic PDFs are parsed locally with page mapping.
    </p>
   </div>
  </div>

  <label className="drop">
   <Upload/>
   <b>Choose PDF files</b>
   <span>Multiple PDFs supported</span>

   <input
    type="file"
    multiple
    accept="application/pdf"
    onChange={e=>setFiles(e.target.files)}
   />
  </label>

  {files.length>0 &&
   <button
    className="primary"
    onClick={upload}
    disabled={busy}
   >
    {busy
     ? 'Parsing…'
     : `Parse ${files.length} PDF(s)`
    }
   </button>
  }

  <div className="doclist">

   {project.documents.map(d=>
    <div key={d.id} className="documentrow">

     <FileText/>

     <b>{d.name}</b>

     <span>{d.pages} pages</span>

     <CheckCircle2/>

     <button
      className="documentdelete"
      title="Remove document"
      onClick={()=>removeDocument(d)}
     >
      <Trash2 size={16}/>
     </button>

    </div>
   )}

  </div>

  <div className="actions">
   <button
    className="primary"
    disabled={!project.documents.length}
    onClick={()=>setPage('plan')}
   >
    Continue to extraction plan
    <ChevronRight/>
   </button>
  </div>

 </section>
}
function Plan({ project, pid, setPage, reload, fail }) {
  const [fields, setFields] = useState(
      project.fields.map((x) => ({ name: x.name, type: x.type })),
    ),
    [model, setModel] = useState('qwen2.5:7b'),
    [busy, setBusy] = useState(false);
  useEffect(
    () =>
      setFields(project.fields.map((x) => ({ name: x.name, type: x.type }))),
    [project.fields.length],
  );
  async function gen() {
    setBusy(true);
    try {
      let x = await call(`/projects/${pid}/plan/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });
      setFields(x.fields);
    } catch (e) {
      fail(e.message);
    }
    setBusy(false);
  }
  async function save() {
    try {
      await call(`/projects/${pid}/plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields }),
      });
      await reload();
      setPage('evidence');
    } catch (e) {
      fail(e.message);
    }
  }
  return (
    <section className="card wide">
      <h2>Define what to extract</h2>
      <p>
        Calvad can propose fields from your research question. You approve the
        plan before extraction.
      </p>
      <div className="modelrow">
        <label>
          Local model
          <input value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <button onClick={gen} disabled={busy}>
          <Sparkles />
          {busy ? 'Asking model…' : 'Generate extraction plan'}
        </button>
      </div>
      {fields.map((f, i) => (
        <div className="fieldrow" key={i}>
          <input
            value={f.name}
            onChange={(e) => {
              let a = [...fields];
              a[i].name = e.target.value;
              setFields(a);
            }}
          />
          <select
            value={f.type}
            onChange={(e) => {
              let a = [...fields];
              a[i].type = e.target.value;
              setFields(a);
            }}
          >
            <option>text</option>
            <option>numeric</option>
            <option>categorical</option>
          </select>
          <button
            className="icon"
            onClick={() => setFields(fields.filter((_, j) => j !== i))}
          >
            ×
          </button>
        </div>
      ))}
      <button
        onClick={() =>
          setFields([...fields, { name: 'New field', type: 'text' }])
        }
      >
        <Plus />
        Add field
      </button>
      <div className="actions">
        <button className="primary" disabled={!fields.length} onClick={save}>
          Approve plan
        </button>
      </div>
    </section>
  );
}
function Evidence({ project, pid, fail }) {
  const [rows, setRows] = useState([]),
    [selected, setSelected] = useState(null),
    [page, setPageText] = useState(null),
    [busy, setBusy] = useState(false),
    [model, setModel] = useState('qwen2.5:7b');
    const load = () =>
    call(`/projects/${pid}/evidence`).then((data) => {
        console.log('CALVAD EVIDENCE ROWS:', data);
        console.log('CALVAD EVIDENCE COUNT:', data.length);
        setRows(data);
    });
      useEffect(() => {
    load();
    }, [pid]);
  async function run() {
    setBusy(true);
    try {
      await call(`/projects/${pid}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });
      await load();
    } catch (e) {
      fail(e.message);
    }
    setBusy(false);
  }
  async function select(r) {
    setSelected(r);
    if (r.page)
      setPageText(await call(`/documents/${r.document_id}/page/${r.page}`));
    else setPageText(null);
  }
  async function review(action) {
    let value = null;
    if (action === 'correct')
      value = prompt('Corrected value:', selected.value);
    if (action === 'correct' && value === null) return;
    await call(`/evidence/${selected.id}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, value }),
    });
    await load();
    setSelected({
      ...selected,
      status:
        action === 'correct'
          ? 'corrected'
          : action === 'reject'
            ? 'rejected'
            : 'accepted',
      value: value ?? selected.value,
    });
  }
  let docs = [...new Set(rows.map((r) => r.document_name))],
    fields = project.fields;
  let map = {};
  rows.forEach((r) => (map[r.document_name + '|' + r.field_name] = r));
  return (
    <>
      <section className="card wide">
        <div className="sectionhead">
          <div>
            <h2>Evidence table</h2>
            <p>
            Calvad first matches the model-supplied evidence to the source document,
            then applies deterministic validation checks. Human review remains a
            separate final step.
            </p>
          </div>
          <div className="toolbar">
            <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            title="Select local Ollama model"
            >
            <option value="qwen2.5:3b">Qwen 2.5 3B — faster</option>
            <option value="qwen2.5:7b">Qwen 2.5 7B — better extraction</option>
            </select>
            <button
              className="primary"
              onClick={run}
              disabled={busy || !fields.length}
            >
        {busy ? 'Extracting & validating…' : 'Run extraction'}
            </button>
            <a href={`${API}/projects/${pid}/export.csv`}>
              <Download />
              CSV
            </a>
            <a href={`${API}/projects/${pid}/export.json`}>
              <Download />
              JSON
            </a>
          </div>
        </div>
        {rows.length ? (
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Study</th>
                    {fields.map((f, i) => (
                    <th key={f.id || `${f.name}-${i}`}>{f.name}</th>
                    ))}
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d}>
                    <th>{d}</th>
                    {fields.map((f) => {
                    let r = map[d + '|' + f.name];

                    return (
                        <td
                        key={f.id || f.name}
                        onClick={() => r && select(r)}
                        className={
                            r?.status === 'missing'
                            ? 'dropped'
                            : r?.validated
                                ? 'verified'
                                : ''
                        }
                        >
                        <div>{r?.value || '—'}</div>

                        {r?.status === 'missing' ? (
                            <small>Missing</small>
                        ) : r ? (
                            <small>
                            {r.source_matched ? 'Source matched' : 'Source not matched'}
                            {' · '}
                            {r.validated ? 'Validated' : 'Not validated'}
                            {' · '}
                            {r.status === 'accepted'
                                ? 'Accepted'
                                : r.status === 'corrected'
                                ? 'Corrected'
                                : r.status === 'rejected'
                                    ? 'Rejected'
                                    : 'Pending review'}
                            </small>
                        ) : null}
                        </td>
                    );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty">
            Approve a plan and run extraction to populate the evidence table.
          </div>
        )}
      </section>
      {selected && (
        <section className="inspector">
          <div className="card">
            <div className="sectionhead">
            <h2>{selected.field_name}</h2>

            <span
                className={
                'pill ' +
                (selected.status === 'accepted' || selected.status === 'corrected'
                    ? 'ok'
                    : selected.status === 'rejected' || selected.status === 'missing'
                    ? 'bad'
                    : '')
                }
            >
                {selected.status === 'accepted'
                ? 'Accepted'
                : selected.status === 'corrected'
                    ? 'Corrected'
                    : selected.status === 'rejected'
                    ? 'Rejected'
                    : selected.status === 'missing'
                        ? 'Missing'
                        : 'Pending review'}
            </span>
            </div>

            <div className="facts">

            <div>
                <small>Extracted value</small>
                <b>{selected.value || 'No value'}</b>
            </div>

            <div>
                <small>Source match</small>
                <b>
                {selected.source_matched
                    ? '✓ Source matched'
                    : '✕ Source not matched'}
                </b>
            </div>

            <div>
                <small>Deterministic validation</small>
                <b>
                {selected.validated
                    ? '✓ Validated'
                    : '✕ Not validated'}
                </b>
            </div>

            <div>
                <small>Human review</small>
                <b>
                {selected.status === 'accepted'
                    ? 'Accepted'
                    : selected.status === 'corrected'
                    ? 'Corrected'
                    : selected.status === 'rejected'
                        ? 'Rejected'
                        : selected.status === 'missing'
                        ? 'Not available'
                        : 'Pending'}
                </b>
            </div>

            <div>
                <small>Source</small>
                <b>
                {selected.document_name}
                {selected.page ? `, p. ${selected.page}` : ''}
                </b>
            </div>

            </div>

            {selected.validation_reason && (
            <div className="validationnote">
                <small>Validation result</small>
                <div>{selected.validation_reason}</div>
            </div>
            )}
            {selected.evidence && <blockquote>{selected.evidence}</blockquote>}
            {selected.reason && (
              <div className="warning">{selected.reason}</div>
            )}
            {selected.status !== 'missing' && (
            <div className="review">
                <button
                className="primary"
                onClick={() => review('accept')}
                >
                Accept
                </button>

                <button onClick={() => review('correct')}>
                Correct
                </button>

                <button
                className="danger"
                onClick={() => review('reject')}
                >
                Reject
                </button>
            </div>
            )}
          </div>
          <div className="card source">
            <h3>Source page</h3>
            {page ? (
              <Highlighted text={page.text} quote={selected.evidence} />
            ) : (
            <div className="empty">No source-matched page available.</div>
            )}
          </div>
        </section>
      )}
    </>
  );
}
function Highlighted({ text, quote }) {
  let q = (quote || '').trim();
  if (!q) return <pre>{text}</pre>;
  let i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return <pre>{text}</pre>;
  return (
    <pre>
      {text.slice(0, i)}
      <mark>{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </pre>
  );
}
function Synthesis({ pid, fail }) {
  const [text, setText] = useState(''),
    [model, setModel] = useState('qwen2.5:7b'),
    [busy, setBusy] = useState(false);
    useEffect(() => {
    call(`/projects/${pid}/synthesis`).then((x) => {
        if (x) {
        setText(x.text || '');
        }
    });
    }, [pid]);
  async function gen() {
    setBusy(true);
    try {
      let x = await call(`/projects/${pid}/synthesis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model }),
      });
      setText(x.text);
    } catch (e) {
      fail(e.message);
    }
    setBusy(false);
  }
  return (
    <section className="card wide">
      <div className="sectionhead">
        <div>
          <h2>Research synthesis</h2>
            <p>
            Generated only from source-matched, validated evidence that has been
            accepted or corrected by the researcher.
            </p>
        </div>
        <div className="toolbar">
          <input value={model} onChange={(e) => setModel(e.target.value)} />
          <button className="primary" onClick={gen} disabled={busy}>
            <Sparkles />
            {busy ? 'Generating…' : 'Generate synthesis'}
          </button>
        </div>
      </div>
      {text ? (
        <article className="synthesis">{text}</article>
      ) : (
        <div className="empty">No synthesis generated yet.</div>
      )}
    </section>
  );
}
function Audit({ pid }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    call(`/projects/${pid}/audit`).then(setRows);
  }, [pid]);
  return (
    <section className="card wide">
      <h2>Audit log</h2>
      <p>Recorded actions, model usage and researcher interventions.</p>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Event</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
        {rows.map((r, i) => (
            <tr key={r.id || i}>
                  <td>{r.ts.replace('T', ' ')}</td>
              <td>
                <b>{r.event}</b>
              </td>
              <td>{r.details}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
createRoot(document.getElementById('root')).render(<App />);