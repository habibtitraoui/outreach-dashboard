import crypto from 'node:crypto';
import { get, put } from '@vercel/blob';
import { google } from 'googleapis';
import { Client as QStashClient, Receiver } from '@upstash/qstash';

const STORE = 'outreach-v1';
const EMAIL = /^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$/i;
const DEFAULT_SETTINGS = {
  sender_name: 'Titraoui Habib', sender_title: 'Software Engineer', company_name: 'EduFormation',
  website: 'https://formation-agency.vercel.app/', demo_link: 'https://formation-agency.vercel.app/',
  whatsapp: '+213 667 807 146', phone: '+213 667 807 146', postal_address: 'Setif, Algeria',
  calendar_link: '', from_email: 'maisterhb@gmail.com', reply_to: 'maisterhb@gmail.com',
  bcc_self: true, bilingual: false, subject_template: '',
  subject_patterns: ['{org} — {hook}', '{hook} — {org}', '{org}: {hook}'], delay_min: 45, delay_max: 90, daily_cap: 35,
};
const CANON = {
  A: 'Replace WhatsApp/Drive video sharing: private courses, progress tracking, auto certificates (EN/AR RTL UI)',
  B: 'Self-paced video lessons per level, EN/AR interface, level-completion certificates',
  C: 'Staff/client compliance training portal: completion tracking and branded certificates for audits',
  D: 'White-label alternative: signed private playback + per-viewer watermark to protect paid content',
  E: 'Branded e-learning portal with admin analytics and category certificates',
};
const DEFAULT_TEMPLATES = {
  A: { hooks: ['private course delivery', 'progress and completion records'], pain: ['Course videos shared over WhatsApp or Drive quickly become hard to control, and there is no clear view of progress or completion.'], solution: 'EduFormation gives your centre a branded private learning portal for the courses you already run.', bullets: ['Private learner access and signed video links', 'Progress, watch-time and automatic certificates', 'Arabic, French and English learner interface'] },
  B: { hooks: ['self-paced lessons by level', 'level completion certificates'], pain: ['Running courses across levels is much easier when learners can resume lessons themselves and see a clear path to completion.'], solution: 'EduFormation organises recorded lessons into branded, self-paced learning paths.', bullets: ['Levels and categories for every course', 'Resume watching from the last lesson', 'Personal learner dashboards and certificates'] },
  C: { hooks: ['audit-ready completion records', 'branded compliance certificates'], pain: ['For training that supports compliance or onboarding, proving who completed what is often more difficult than delivering the course.'], solution: 'EduFormation turns your existing material into a branded portal with completion evidence.', bullets: ['Per-learner completion and watch time', 'Audit-ready training records', 'Branded certificates for completed courses'] },
  D: { hooks: ['private video protection', 'a portal you own'], pain: ['Paid recordings lose value when files can be forwarded, downloaded or shared outside the intended learners.'], solution: 'EduFormation gives you a white-label place to deliver paid content with controlled playback.', bullets: ['Signed private playback links', 'Per-viewer watermark support', 'A branded portal instead of public file sharing'] },
  E: { hooks: ['course analytics and certificates', 'a branded learning portal'], pain: ['When recorded courses are spread across tools, it is difficult to see what learners actually watch or complete.'], solution: 'EduFormation brings recorded training into one branded portal with useful reporting.', bullets: ['Learner, video and completion analytics', 'Categories for your course library', 'Branded completion certificates'] },
};
const GREETINGS = ['Hello {org} team,', 'Hi {org} team,', 'Hello {org},', 'Good morning {org} team,'];
const CTAS = ['Worth 15 minutes this week? Reply to this email and I will show you your own courses running inside it.', 'Can I show you this on your own content? Reply with a course name and I will set the demo up around it.', 'If this is useful, reply and I will walk you through it in 15 minutes, using your own material.'];

function now() { return new Date().toISOString(); }
function json(res, status, payload) { res.status(status).setHeader('Cache-Control', 'no-store').json(payload); }
function key(name) { return `${STORE}/${name}.json`; }
async function read(name, fallback) {
  if (!process.env.BLOB_READ_WRITE_TOKEN) throw new Error('BLOB_READ_WRITE_TOKEN is not configured.');
  const blob = await get(key(name), { access: 'private', token: process.env.BLOB_READ_WRITE_TOKEN });
  if (!blob) return structuredClone(fallback);
  const response = await fetch(blob.url, { headers: { Authorization: `Bearer ${process.env.BLOB_READ_WRITE_TOKEN}` } });
  if (!response.ok) return structuredClone(fallback);
  return response.json();
}
async function write(name, data) {
  await put(key(name), JSON.stringify(data), { access: 'private', addRandomSuffix: false, contentType: 'application/json', token: process.env.BLOB_READ_WRITE_TOKEN });
  return data;
}
function oauth(req) {
  const redirect = process.env.GOOGLE_REDIRECT_URI || `${origin(req)}/api/google/callback`;
  return new google.auth.OAuth2(process.env.GOOGLE_CLIENT_ID, process.env.GOOGLE_CLIENT_SECRET, redirect);
}
function origin(req) { return process.env.APP_URL || `${req.headers['x-forwarded-proto'] || 'https'}://${req.headers['x-forwarded-host'] || req.headers.host}`; }
function crypt(value, decrypt = false) {
  const secret = process.env.OAUTH_TOKEN_ENCRYPTION_KEY;
  if (!secret) throw new Error('OAUTH_TOKEN_ENCRYPTION_KEY is not configured.');
  const k = crypto.createHash('sha256').update(secret).digest();
  if (!decrypt) { const iv = crypto.randomBytes(12), c = crypto.createCipheriv('aes-256-gcm', k, iv); const text = Buffer.concat([c.update(value, 'utf8'), c.final()]); return [iv.toString('base64'), c.getAuthTag().toString('base64'), text.toString('base64')].join('.'); }
  const [iv, tag, text] = value.split('.').map(x => Buffer.from(x, 'base64')); const c = crypto.createDecipheriv('aes-256-gcm', k, iv); c.setAuthTag(tag); return Buffer.concat([c.update(text), c.final()]).toString('utf8');
}
async function gmail(req) { const saved = await read('gmail-token', null); if (!saved) throw new Error('Gmail is not connected. Use Connect Gmail in Send options.'); const client = oauth(req); client.setCredentials(JSON.parse(crypt(saved, true))); return google.gmail({ version: 'v1', auth: client }); }
function hash(s) { let n = 0; for (const c of String(s).toLowerCase()) n = (n * 131 + c.charCodeAt(0)) % 1000003; return n; }
function pick(a, seed, salt) { return a[(seed * 31 + salt * 17 + 7) % a.length]; }
function render(lead, settings, templates, overrides) {
  const custom = overrides[String(lead.n)]; if (custom?.subject || custom?.body) return [custom.subject || '', custom.body || ''];
  const t = templates[lead.archetype] || DEFAULT_TEMPLATES.A, seed = hash(lead.email || lead.organisation), org = lead.organisation || 'your team';
  const hook = pick(t.hooks, seed, 1), subject = (settings.subject_template || pick(settings.subject_patterns, seed, 2)).replaceAll('{org}', org).replaceAll('{hook}', hook).replaceAll('{city}', lead.city || '').replaceAll('{country}', lead.country || '');
  const greeting = pick(GREETINGS, seed, 3).replace('{org}', org);
  const demo = settings.demo_link || settings.website;
  const body = [greeting, '', `I came across ${org} while mapping training providers in ${lead.city ? `${lead.city}, ` : ''}${lead.country || 'the Gulf'}.`, '', pick(t.pain, seed, 4), '', t.solution, '', 'In practice that means:', ...t.bullets.map(x => `  -  ${x}`), '', 'We set the portal up under your own brand and migrate the videos you already have.', '', pick(CTAS, seed, 5), demo ? `\nThe live demo is here if you prefer to look before talking: ${demo}` : '', '', 'Kind regards,', settings.sender_name, `${settings.sender_title}, ${settings.company_name}`, `WhatsApp ${settings.whatsapp}  ·  ${settings.from_email}`, '', `You are receiving this one-off email because ${org} is publicly listed as a training provider${lead.country ? ` in ${lead.country}` : ''}. If you would prefer not to hear from me again, reply with "stop" and I will remove you and confirm.`].filter(Boolean).join('\n');
  return [subject, body];
}
function lint(subject, body) { const out = []; const links = (body.match(/https?:\/\/\S+/g) || []).length; if (links > 2) out.push({ level: 'warn', msg: `${links} links in the body. Keep it to 1–2.` }); if (subject.length > 78) out.push({ level: 'info', msg: 'Subject is long for mobile.' }); out.push({ level: 'ok', msg: 'Plain-text message ready for review.' }); return out; }
function csvRows(text) {
  const lines = String(text).replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean); const delimiter = [',', ';', '\t', '|'].sort((a,b) => lines[0].split(b).length - lines[0].split(a).length)[0];
  const cells = line => line.split(delimiter).map(x => x.trim().replace(/^"|"$/g, ''));
  const headers = cells(lines.shift()).map(x => x.toLowerCase().replace(/[^a-z0-9]/g, ''));
  const aliases = { n:['n','id','no','number'], organisation:['organisation','organization','org','company','companyname','name','academy','school'], segment:['segment','category','type','industry'], country:['country','nation'], city:['city','town','location'], phone:['phone','mobile','tel','whatsapp'], email:['email','emailaddress','mail'], website:['website','web','url'], rating:['rating','stars'], reviews:['reviews','reviewcount'], priority:['priority'], pitch_angle:['pitchangle','pitch','angle','hook','needs'], status:['status'], notes:['notes','description','details'] };
  const index = field => headers.findIndex(h => (aliases[field] || []).includes(h)); const at = (row, f) => { const i = index(f); return i < 0 ? '' : row[i] || ''; };
  const rows = lines.map((line, i) => { const r = cells(line); const blob = ['segment','pitch_angle','notes','organisation'].map(f => at(r,f)).join(' ').toLowerCase(); let archetype = /watermark|drm|piracy|protect/.test(blob) ? 'D' : /compliance|audit|safety|iso/.test(blob) ? 'C' : /language|ielts|level|self.paced/.test(blob) ? 'B' : /analytics|reporting|lms/.test(blob) ? 'E' : 'A'; return { n: at(r,'n') || String(i + 1), organisation: at(r,'organisation'), segment: at(r,'segment') || 'Training centre', country: at(r,'country'), city: at(r,'city'), phone: at(r,'phone'), email: at(r,'email').replace(/\s/g,'').toLowerCase(), website: at(r,'website'), rating: at(r,'rating'), reviews: at(r,'reviews'), priority: at(r,'priority'), pitch_angle: at(r,'pitch_angle') || CANON[archetype], status: at(r,'status'), notes: at(r,'notes'), archetype }; }).filter(r => r.organisation || r.email);
  const seen = new Set(), deduped = rows.filter(r => !r.email || (!seen.has(r.email) && seen.add(r.email))); return { rows: deduped, report: { rows: deduped.length, emailable: deduped.filter(r => EMAIL.test(r.email)).length, duplicates_merged: rows.length - deduped.length, invalid_emails: rows.filter(r => r.email && !EMAIL.test(r.email)).map(r => r.email), angles_inferred: rows.filter(r => !r.pitch_angle).length, delimiter } };
}
function logLine(run, msg, level = 'info') { run.log = [...(run.log || []), { t: new Date().toLocaleTimeString('en-GB', { hour12: false }), msg, level }].slice(-400); }
async function schedule(req, job, delay = 0) { if (!process.env.QSTASH_TOKEN) throw new Error('QSTASH_TOKEN is not configured.'); const q = new QStashClient({ token: process.env.QSTASH_TOKEN }); await q.publishJSON({ url: `${origin(req)}/api/worker`, body: job, delay }); }
async function sendRaw(req, to, subject, body, settings) {
  const headers = [`From: ${settings.sender_name} <${settings.from_email}>`, `To: ${to}`, `Reply-To: ${settings.reply_to || settings.from_email}`, `Subject: ${subject}`, 'MIME-Version: 1.0', 'Content-Type: text/plain; charset="UTF-8"', 'List-Unsubscribe: <mailto:' + settings.from_email + '?subject=unsubscribe>', 'List-Unsubscribe-Post: List-Unsubscribe=One-Click'];
  const raw = Buffer.from(`${headers.join('\r\n')}\r\n\r\n${body}`).toString('base64url'); await (await gmail(req)).users.messages.send({ userId: 'me', requestBody: { raw } });
  if (settings.bcc_self) { const copy = headers.map(x => x.startsWith('To: ') ? `To: ${settings.from_email}` : x).join('\r\n'); await (await gmail(req)).users.messages.send({ userId: 'me', requestBody: { raw: Buffer.from(`${copy}\r\n\r\n${body}`).toString('base64url') } }); }
}
async function worker(req, res) {
  const receiver = new Receiver({ currentSigningKey: process.env.QSTASH_CURRENT_SIGNING_KEY, nextSigningKey: process.env.QSTASH_NEXT_SIGNING_KEY });
  const raw = typeof req.body === 'string' ? req.body : JSON.stringify(req.body || {}); const valid = await receiver.verify({ signature: req.headers['upstash-signature'], body: raw, url: `${origin(req)}/api/worker` }).catch(() => false); if (!valid) return json(res, 401, { error: 'Invalid queue signature.' });
  const run = await read('run', null); if (!run?.running || run.id !== req.body?.runId || run.stop) return json(res, 200, { ok: true });
  const data = await read('data', { leads: [], dataset: {} }); const settings = { ...DEFAULT_SETTINGS, ...await read('settings', {}) }, templates = { ...DEFAULT_TEMPLATES, ...await read('templates', {}) }, overrides = await read('overrides', {}), logs = await read('activity', []); const lead = data.leads[run.index];
  if (!lead) { run.running = false; run.finished = now(); logLine(run, `Run finished — sent ${run.ok}, failed ${run.fail}.`, 'ok'); await write('run', run); return json(res, 200, { ok: true }); }
  const [subject, body] = render(lead, settings, templates, overrides); run.current = `${lead.organisation} <${lead.email}>`;
  try { if (run.mode !== 'dry') await sendRaw(req, run.mode === 'test' ? run.test_to : lead.email, subject, body, settings); run.ok++; logs.push({ timestamp: now(), n: lead.n, organisation: lead.organisation, email: lead.email, subject, status: run.mode === 'test' ? 'TEST' : run.mode === 'dry' ? 'DRY' : 'SENT' }); logLine(run, `✓ ${run.index + 1}/${run.total} → ${lead.email}`, 'ok'); } catch (error) { run.fail++; logs.push({ timestamp: now(), n: lead.n, organisation: lead.organisation, email: lead.email, subject, status: 'FAILED', detail: String(error.message).slice(0, 200) }); logLine(run, `✕ ${lead.email} — ${error.message}`, 'err'); }
  run.index++; run.current = ''; if (run.index >= run.total) { run.running = false; run.finished = now(); logLine(run, `Run finished — sent ${run.ok}, failed ${run.fail}.`, 'ok'); await Promise.all([write('run', run), write('activity', logs.slice(-1000))]); return json(res, 200, { ok: true }); }
  const gap = run.mode === 'dry' ? 1 : Math.max(1, Math.round(Number(run.delay_min) + Math.random() * Math.max(0, Number(run.delay_max) - Number(run.delay_min)))); logLine(run, `Waiting ${gap}s …`); await Promise.all([write('run', run), write('activity', logs.slice(-1000))]); await schedule(req, { runId: run.id }, gap); return json(res, 200, { ok: true });
}
export default async function handler(req, res) {
  try {
    const route = Array.isArray(req.query.route) ? req.query.route.join('/') : req.query.route || '';
    if (route === 'worker' && req.method === 'POST') return worker(req, res);
    if (route === 'google/connect') { const url = oauth(req).generateAuthUrl({ access_type: 'offline', prompt: 'consent', scope: ['https://www.googleapis.com/auth/gmail.send'] }); return res.redirect(302, url); }
    if (route === 'google/callback') { const client = oauth(req); const { tokens } = await client.getToken(req.query.code); if (!tokens.refresh_token) throw new Error('Google did not return a refresh token. Remove this app from Google Account permissions and connect again.'); await write('gmail-token', crypt(JSON.stringify(tokens))); return res.redirect(302, '/?gmail=connected'); }
    if (route === 'google/status') return json(res, 200, { connected: !!await read('gmail-token', null) });
    if (route === 'state' && req.method === 'GET') { const data = await read('data', { leads: [], dataset: {} }), overrides = await read('overrides', {}), activity = await read('activity', []), settings = { ...DEFAULT_SETTINGS, ...await read('settings', {}) }, run = await read('run', { running: false }); const sent = new Set(activity.filter(x => x.status === 'SENT' || x.status === 'TEST').map(x => x.email.toLowerCase())); const leads = data.leads.map(l => ({ ...l, sendable: EMAIL.test(l.email), sent: sent.has(l.email.toLowerCase()), custom: !!overrides[String(l.n)] })); const angles = Object.fromEntries(Object.keys(CANON).map(k => [k, { count: leads.filter(x => x.archetype === k).length, angle: k }])); const today = now().slice(0,10); return json(res, 200, { leads, overrides: Object.keys(overrides).length, dataset: data.dataset || {}, duplicate_bodies: 0, stats: { total: leads.length, sendable: leads.filter(x => x.sendable).length, no_email: leads.filter(x => !x.sendable).length, sent: leads.filter(x => x.sent).length, countries: [...new Set(leads.map(x => x.country).filter(Boolean))].sort() }, angles, settings, has_password: false, password_source: null, gmail_connected: !!await read('gmail-token', null), sent_today: activity.filter(x => x.status === 'SENT' && x.timestamp.startsWith(today)).length, daily_cap: Number(settings.daily_cap) || 35, one_click_ready: !!await read('gmail-token', null), running: !!run.running }); }
    if (route === 'preview' && req.method === 'GET') { const data = await read('data', { leads: [] }), lead = data.leads.find(x => String(x.n) === String(req.query.n)); if (!lead) return json(res, 404, { error: 'not found' }); const settings = { ...DEFAULT_SETTINGS, ...await read('settings', {}) }, overrides = await read('overrides', {}), [subject, body] = render(lead, settings, { ...DEFAULT_TEMPLATES, ...await read('templates', {}) }, overrides); return json(res, 200, { n: lead.n, to: lead.email, from: settings.from_email, organisation: lead.organisation, subject, body, angle: lead.archetype, custom: !!overrides[String(lead.n)], checks: lint(subject, body) }); }
    if (route === 'templates' && req.method === 'GET') { const all = { ...DEFAULT_TEMPLATES, ...await read('templates', {}) }; return json(res, 200, { angles: Object.entries(all).map(([key, x]) => ({ key, pains: x.pain, solution: x.solution, bullets: x.bullets, hooks: x.hooks })) }); }
    if (route === 'templates' && req.method === 'POST') return json(res, 200, { ok: true, templates: await write('templates', req.body.templates || {}) });
    if (route === 'settings' && req.method === 'POST') { const next = { ...DEFAULT_SETTINGS, ...await read('settings', {}), ...req.body }; return json(res, 200, { ok: true, settings: await write('settings', next) }); }
    if (route === 'override' && req.method === 'POST') { const values = await read('overrides', {}), n = String(req.body.n || ''); if (!n) return json(res, 400, { error: 'row number required' }); if (req.body.clear) delete values[n]; else values[n] = { subject: String(req.body.subject || '').trim(), body: String(req.body.body || '').trim(), saved_at: now() }; await write('overrides', values); return json(res, 200, { ok: true, custom: !!values[n] }); }
    if (route === 'upload' && req.method === 'POST') { const parsed = csvRows(req.body.csv || ''); if (!parsed.rows.length) return json(res, 400, { error: 'No usable rows found — is that the right file?' }); const dataset = { file: 'cloud-storage', label: String(req.body.filename || 'leads.csv'), uploaded: now(), report: parsed.report }; await write('data', { leads: parsed.rows, dataset }); return json(res, 200, { ok: true, report: parsed.report, dataset }); }
    if (route === 'activity' && req.method === 'GET') return json(res, 200, { rows: (await read('activity', [])).slice(-300).reverse() });
    if (route === 'progress' && req.method === 'GET') return json(res, 200, await read('run', { running: false, log: [] }));
    if (route === 'smtp-check' && req.method === 'POST') return json(res, 200, { ok: !!await read('gmail-token', null), msg: (await read('gmail-token', null)) ? 'Gmail is connected and ready to send through the Gmail API.' : 'Gmail is not connected. Use Connect Gmail.' });
    if (route === 'secret' && req.method === 'POST') return json(res, 400, { error: 'App passwords are not used on the hosted dashboard. Connect Gmail with OAuth instead.' });
    if (route === 'send' && req.method === 'POST') { const current = await read('run', { running: false }); if (current.running) return json(res, 409, { error: 'already running' }); const mode = req.body.mode || 'dry'; if ((mode === 'live' || mode === 'test') && !await read('gmail-token', null)) return json(res, 400, { error: 'Connect Gmail before sending.' }); if (mode === 'test' && !req.body.test_to) return json(res, 400, { error: 'test recipient required' }); const data = await read('data', { leads: [] }), activity = await read('activity', []), sent = new Set(activity.filter(x => x.status === 'SENT').map(x => x.email.toLowerCase())); let leads = data.leads.filter(x => EMAIL.test(x.email)); if (req.body.country) leads = leads.filter(x => x.country === req.body.country); if (req.body.only?.length) leads = leads.filter(x => req.body.only.includes(x.archetype)); if (mode === 'live') leads = leads.filter(x => !sent.has(x.email.toLowerCase())); if (mode === 'test') leads = leads.filter((x, i, a) => a.findIndex(y => y.archetype === x.archetype) === i); const limit = Number(req.body.limit) || (mode === 'live' ? Math.max(0, (Number((await read('settings', {})).daily_cap) || 35) - activity.filter(x => x.status === 'SENT' && x.timestamp.startsWith(now().slice(0,10))).length) : 0); if (limit) leads = leads.slice(0, limit); await write('data', { leads, dataset: data.dataset }); const run = { id: crypto.randomUUID(), running: true, mode, total: leads.length, index: 0, ok: 0, fail: 0, skipped: 0, current: '', started: now(), finished: null, log: [{ t: new Date().toLocaleTimeString('en-GB', { hour12: false }), msg: `Started ${mode} run — ${leads.length} message(s).`, level: 'info' }], stop: false, delay_min: req.body.delay_min || 45, delay_max: req.body.delay_max || 90, test_to: req.body.test_to || '' }; await write('run', run); if (!leads.length) { run.running = false; run.finished = now(); await write('run', run); return json(res, 200, { ok: true }); } await schedule(req, { runId: run.id }); return json(res, 200, { ok: true }); }
    if (route === 'stop' && req.method === 'POST') { const run = await read('run', { running: false }); run.stop = true; await write('run', run); return json(res, 200, { ok: true }); }
    return json(res, 404, { error: 'Not found' });
  } catch (error) { console.error(error); return json(res, 500, { error: error.message || 'Server error' }); }
}
