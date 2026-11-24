import { useEffect, useRef, useState } from 'react';
import { FileText, UploadCloud, RefreshCw, CheckCircle2, AlertCircle, Layers3 } from 'lucide-react';

const extensions = '.pdf,.jpg,.jpeg,.png,.tiff,.tif,.xlsx,.xls,.csv';
function fmtBytes(size) { return size < 1024 ? `${size} B` : size < 1048576 ? `${(size/1024).toFixed(1)} KB` : `${(size/1048576).toFixed(1)} MB`; }

export default function App() {
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem('careguide_api_key') || '');
  function updateApiKey(value) { setApiKey(value); sessionStorage.setItem('careguide_api_key', value); }
  function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (apiKey) headers.set('X-API-Key', apiKey);
    return fetch(url, {...options, headers});
  }

  const picker = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [selected, setSelected] = useState(null);
  const [resultData, setResultData] = useState(null);
  const [actionId, setActionId] = useState(null);
  const [invoiceData, setInvoiceData] = useState(null);
  const [invoiceError, setInvoiceError] = useState('');
  const [edits, setEdits] = useState({});
  const [compareId, setCompareId] = useState('');
  const [comparison, setComparison] = useState(null);
  const [saving, setSaving] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchMode, setSearchMode] = useState('keyword');
  async function searchDocuments(event) {
    event.preventDefault();
    if (searchText.trim().length < 2) { setError('Enter at least 2 characters to search.'); return; }
    setSearchBusy(true); setError('');
    try {
      const res = await apiFetch(`${searchMode==='semantic'?'/api/search/semantic':'/api/search'}?${new URLSearchParams({q:searchText.trim()})}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || `Search HTTP ${res.status}`);
      setSearchResults(body);
    } catch (err) {setError(err.message);} finally {setSearchBusy(false);}
  }
  async function refresh() {
    setLoading(true);
    try {
      const res = await apiFetch('/api/documents');
      if (!res.ok) throw new Error(`Could not load documents (${res.status})`);
      setDocuments(await res.json()); setError('');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer); }, [apiKey]);
  async function processDoc(doc) {
    setActionId(doc.id); setError('');
    try {
      const res = await apiFetch(`/api/documents/${doc.id}/process`, {method:'POST'});
      if (!res.ok) { const data=await res.json().catch(()=>({})); throw new Error(data.detail || `HTTP ${res.status}`); }
      setMessage(`${doc.original_filename} queued for processing.`);
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setActionId(null); }
  }
  async function showResult(doc) {
    setSelected(doc); setResultData(null); setInvoiceData(null); setComparison(null); setCompareId(''); setInvoiceError(''); setError('');
    try {
      const res = await apiFetch(`/api/documents/${doc.id}/result`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResultData(await res.json());
      const invoiceResponse = await apiFetch(`/api/documents/${doc.id}/invoice`);
      if (invoiceResponse.ok) {
        const data=await invoiceResponse.json(); setInvoiceData(data); setEdits(data.invoice.fields);
      } else if (invoiceResponse.status!==409) {
        setInvoiceError(`Invoice request failed (${invoiceResponse.status})`);
      }
    } catch (err) { setError(err.message); }
  }
  async function saveInvoice() {
    if (!selected) return;
    setSaving(true); setError('');
    try {
      const res=await apiFetch(`/api/documents/${selected.id}/invoice`,{
        method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(edits)
      });
      if (!res.ok) { const msg=await res.json().catch(()=>({})); throw new Error(msg.detail||`HTTP ${res.status}`); }
      const data=await res.json(); setInvoiceData(data); setEdits(data.invoice.fields); setMessage('Corrections saved and validation updated.');
    } catch (err) {setError(err.message);} finally {setSaving(false);}
  }
  async function compareDocs() {
    if (!selected || !compareId) return;
    setError('');setComparison(null);
    try {
      const params=new URLSearchParams({left_id:selected.id,right_id:compareId});
      const res=await apiFetch(`/api/compare?${params}`);
      if (!res.ok) { const msg=await res.json().catch(()=>({})); throw new Error(msg.detail||`HTTP ${res.status}`); }
      setComparison(await res.json());
    } catch(err) {setError(err.message);}
  }
  async function upload(files) {
    if (!files?.length) return;
    setBusy(true); setError(''); setMessage('');
    let uploaded = 0;
    try {
      for (const file of files) {
        const form = new FormData(); form.append('file', file);
        const res = await apiFetch('/api/documents', { method: 'POST', body: form });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(`${file.name}: ${data.detail || `HTTP ${res.status}`}`);
        }
        uploaded++;
      }
      setMessage(`${uploaded} document${uploaded===1?'':'s'} uploaded successfully.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); if (picker.current) picker.current.value = ''; await refresh(); }
  }
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand"><div className="brand-icon"><Layers3 size={22}/></div><span>Care Guide<br/><small>Document Intelligence</small></span></div>
        <div className="side-link active"><FileText size={18}/> Documents</div>
        <div className="side-bottom">Phase 9 · Reliability & API key<br/><small>Local / Docker-ready starter</small></div>
      </aside>
      <main className="main">
        <header><div><span className="eyebrow">WORKSPACE / DOCUMENTS</span><h1>Document Intelligence</h1><p>Upload, process, and inspect financial documents.</p></div><span className="phase">PHASE 9</span></header>
        <section className="panel" style={{marginBottom:16}}><label>Local API access key (only if configured in your .env)<input aria-label="API access key" type="password" autoComplete="off" value={apiKey} onChange={e=>updateApiKey(e.target.value)} placeholder="Leave blank if API key is disabled" style={{marginLeft:12}} /></label><p className="note">Stored for this browser tab only. Do not use real financial documents without securing access.</p></section>
        <section className="metrics"><div><span>Total documents</span><strong>{documents.length}</strong><small>Stored in database (latest 100)</small></div><div><span>Processed</span><strong>{documents.filter(d=>d.status==='completed').length}</strong><small>Awaiting extraction</small></div><div><span>File formats</span><strong>9</strong><small>PDF · images · spreadsheets</small></div></section>
        <section className="panel upload" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();upload([...e.dataTransfer.files]);}}>
          <div className="upload-icon"><UploadCloud size={27}/></div><h2>Upload your documents</h2><p>Drag and drop files here or select files from your device.</p>
          <input ref={picker} type="file" multiple accept={extensions} hidden onChange={e=>upload([...e.target.files])}/>
          <button disabled={busy} onClick={()=>picker.current?.click()}>{busy?'Uploading…':'Choose files'}</button>
          <small>PDF, JPG, PNG, TIFF, XLSX, XLS, CSV · Maximum 20 MB per file by default</small>
        </section>
        {error && <div role="alert" className="notice error"><AlertCircle size={17}/>{error}</div>}
        {message && <div role="status" className="notice success"><CheckCircle2 size={17}/>{message}</div>}
        <section className="panel files"><div className="section-title"><div><h2>Search documents</h2><p>Search filenames/text or use local embedding similarity</p></div></div>
          <form onSubmit={searchDocuments} className="compare-controls"><select aria-label="Search mode" value={searchMode} onChange={e=>{setSearchMode(e.target.value);setSearchResults(null)}}><option value="keyword">Keyword</option><option value="semantic">Semantic</option></select><input aria-label="Search documents" value={searchText} onChange={e=>setSearchText(e.target.value)} placeholder="Search invoice number, supplier, or other text"/><button disabled={searchBusy}>{searchBusy?'Searching…':'Search'}</button></form>
          {searchResults && <><p className="note">{searchResults.count} result(s). {searchResults.note}</p><div className="table-wrap"><table><thead><tr><th>Document</th><th>Matching text</th><th>Action</th></tr></thead><tbody>{searchResults.results.map(hit=><tr key={hit.document_id}><td>{hit.filename}</td><td>{hit.snippet||'(Filename match)'}{typeof hit.score==='number' && <small> · similarity {hit.score.toFixed(3)}</small>}</td><td><button className="secondary" onClick={()=>{const doc=documents.find(d=>d.id===hit.document_id);if(doc)showResult(doc);else setError('Document is outside the latest 100 shown in the list.');}}>View</button></td></tr>)}{!searchResults.results.length && <tr><td colSpan="3">No matching documents found.</td></tr>}</tbody></table></div></>}
        </section>
        <section className="panel files"><div className="section-title"><div><h2>Recent documents</h2><p>Uploaded files and processing status</p></div><button className="secondary" disabled={loading} onClick={refresh}><RefreshCw size={16}/> Refresh</button></div>
        <div className="table-wrap"><table><thead><tr><th>File name</th><th>Size</th><th>Status</th><th>Uploaded</th><th>Actions</th></tr></thead><tbody>
          {documents.map(doc=><tr key={doc.id}><td><span className="filename"><FileText size={17}/>{doc.original_filename}</span></td><td>{fmtBytes(doc.size_bytes)}</td><td><span className="status">{doc.status}</span></td><td>{new Date(doc.created_at).toLocaleString()}</td><td><div className="actions"><button className="secondary" disabled={actionId===doc.id || ['queued','processing'].includes(doc.status)} onClick={()=>processDoc(doc)}>{actionId===doc.id?'Queuing...':doc.status==='completed'?'Reprocess':'Process'}</button><button className="secondary" onClick={()=>showResult(doc)}>View result</button></div></td></tr>)}
          {!documents.length && <tr><td className="empty" colSpan="5">No documents yet. Upload a file to get started.</td></tr>}
        </tbody></table></div></section>
        {selected && <section className="panel result-panel"><div className="section-title"><div><h2>Extraction result: {selected.original_filename}</h2><p>Read-only extracted text and file structure</p></div><button className="secondary" onClick={()=>showResult(selected)}><RefreshCw size={16}/> Reload</button></div>
          {!resultData && <p>Loading...</p>}
          {resultData && <><p><strong>Status:</strong> {resultData.status} {resultData.error_message && <span className="failure">— {resultData.error_message}</span>}</p>
          {resultData.result && <><p><strong>Type:</strong> {resultData.result.kind} · <strong>Pages:</strong> {resultData.result.page_count} · <strong>Sheets:</strong> {resultData.result.sheet_count} · <strong>Characters:</strong> {resultData.result.extracted_chars}</p>
          {resultData.result.warning && <p className="note">{resultData.result.warning} {resultData.result.truncated && 'Output was truncated.'}</p>}
          {resultData.result.pdf_tables?.some(p=>p.tables?.length) && <details><summary>Detected PDF tables</summary><pre>{JSON.stringify(resultData.result.pdf_tables.filter(p=>p.tables?.length),null,2)}</pre></details>}
          {resultData.result.semantic_warning && <p className="note">{resultData.result.semantic_warning}</p>}
          {resultData.result.sheets?.length>0 && <details><summary>Spreadsheet previews</summary><pre>{JSON.stringify(resultData.result.sheets, null, 2)}</pre></details>}
          <h3>Extracted text preview</h3><pre className="extract-preview">{resultData.result.text || '(No readable text detected)'}</pre></>}
          {!resultData.result && <p>The file has not completed processing. Status refreshes automatically in the document list.</p>}</>}
          {invoiceError && <p className="failure">{invoiceError}</p>}
          {invoiceData && <div className="invoice-review">
            <h3>Invoice extraction and validation</h3>
            <p className="note">Extraction method: <strong>{invoiceData.invoice.extraction_method}</strong>. Unrecognized values remain blank; verify against the source before saving.</p>
            <div className="invoice-grid">
            {Object.keys(edits).map(field=><label key={field} className="invoice-field"><span>{field.replaceAll('_',' ')}</span><input value={edits[field]??''} placeholder="Not extracted" onChange={e=>setEdits(p=>({...p,[field]:e.target.value||null}))}/></label>)}
            </div>
            <button disabled={saving} onClick={saveInvoice}>{saving?'Saving…':'Save reviewed fields'}</button>
            {invoiceData.invoice.source_coverage && <details><summary>Extraction coverage and limits</summary><pre>{JSON.stringify(invoiceData.invoice.source_coverage, null, 2)}</pre></details>}
            {invoiceData.invoice.warnings?.length>0 && <div className="note"><strong>Extraction review required:</strong><ul>{invoiceData.invoice.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></div>}
            <h3>Extracted line items</h3>
            {invoiceData.invoice.line_items?.length ? <div className="table-wrap"><table><thead><tr><th>Description</th><th>Quantity</th><th>Unit price</th><th>Amount</th></tr></thead><tbody>{invoiceData.invoice.line_items.slice(0,100).map((item,i)=><tr key={i}><td>{item.description}</td><td>{item.quantity??'—'}</td><td>{item.unit_price??'—'}</td><td>{item.amount??'—'}</td></tr>)}</tbody></table></div>:<p className="note">No reliable line-item table detected. The current parser requires recognizable column headers.</p>}
            {invoiceData.invoice.line_items?.length>100 && <p className="note">Showing the first 100 of {invoiceData.invoice.line_items.length} extracted items; all stored items are used for reconciliation.</p>}
            <h3>Validation findings</h3>
            {invoiceData.validation.length===0 ? <p>No rule violations detected. This does not prove the invoice is correct.</p> :
              <ul>{invoiceData.validation.map((v,i)=><li key={i}><strong>{v.code}:</strong> {v.message}</li>)}</ul>}
            <h3>Compare with another processed document</h3>
            <div className="compare-controls"><select value={compareId} onChange={e=>setCompareId(e.target.value)}><option value="">Choose document</option>{documents.filter(d=>d.id!==selected.id&&d.status==='completed').map(d=><option key={d.id} value={d.id}>{d.original_filename} ({d.id.slice(0,8)})</option>)}</select><button disabled={!compareId} onClick={compareDocs}>Compare fields</button></div>
            {comparison && <><p>{comparison.mismatches} differing fields (missing values tracked separately).</p><div className="table-wrap"><table><thead><tr><th>Field</th><th>Left</th><th>Right</th><th>Result</th></tr></thead><tbody>{comparison.fields.map(row=><tr key={row.field}><td>{row.field}</td><td>{row.left??'—'}</td><td>{row.right??'—'}</td><td>{row.status}</td></tr>)}</tbody></table></div><p className="note">{comparison.note}</p>
              <h3>Line-item reconciliation</h3>
              <p><strong>Status:</strong> {comparison.reconciliation_status} · Matched {comparison.line_item_summary?.matched ?? 0} · Mismatched {comparison.line_item_summary?.mismatched ?? 0} · Unpaired {comparison.line_item_summary?.unpaired ?? 0}</p>
              {comparison.line_items?.length>0 && <div className="table-wrap"><table><thead><tr><th>Item</th><th>Left quantity / amount</th><th>Right quantity / amount</th><th>Result</th></tr></thead><tbody>{comparison.line_items.slice(0,100).map((item,i)=><tr key={i}><td>{item.description}</td><td>{item.left ? `${item.left.quantity} / ${item.left.amount}`:'—'}</td><td>{item.right ? `${item.right.quantity} / ${item.right.amount}`:'—'}</td><td>{item.status}</td></tr>)}</tbody></table></div>}
              {comparison.line_items?.length>100 && <p className="note">Showing first 100 of {comparison.line_items.length} compared entries.</p>}
              {comparison.limitations?.map((warning,i)=><p className="note" key={i}>{warning}</p>)}
            </>}
          </div>}
        </section>}
        <footer>Phase 9: API-key option, processing audit trail and failure recovery. Not multi-tenant or production-certified.</footer>
      </main>
    </div>
  );
}
