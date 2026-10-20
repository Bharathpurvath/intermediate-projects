import React, { useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API = 'http://127.0.0.1:8001/api'
const getToken = () => sessionStorage.getItem('margin-token')
async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}), ...options.headers }
  const response = await fetch(`${API}${path}`, { ...options, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Something went wrong. Please try again.')
  }
  return response.status === 204 ? null : response.json()
}
const dateLabel = value => new Intl.DateTimeFormat('en', { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(value))
const readingTime = text => Math.max(1, Math.ceil(text.trim().split(/\s+/).length / 220))

function Icon({ name, size = 18 }) {
  const paths = {
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    close: <><path d="m18 6-12 12M6 6l12 12"/></>,
    arrow: <><path d="M7 17 17 7M7 7h10v10"/></>,
    back: <><path d="m15 18-6-6 6-6"/></>,
    edit: <><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/></>,
    trash: <><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6"/></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/></>
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
function App() {
  const [posts, setPosts] = useState([])
  const [user, setUser] = useState(null)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)
  const [activePost, setActivePost] = useState(null)
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [authMode, setAuthMode] = useState('login')
  const [form, setForm] = useState({ title: '', category: 'Field notes', content: '' })
  const [authForm, setAuthForm] = useState({ name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const refresh = useCallback(async (term = search) => {
    setLoading(true)
    try { setPosts(await request(`/posts${term ? `?search=${encodeURIComponent(term)}` : ''}`)) }
    catch (error) { setNotice(error.message) }
    finally { setLoading(false) }
  }, [search])
  useEffect(() => { refresh('') }, [])
  useEffect(() => {
    if (!getToken()) return
    request('/auth/me').then(setUser).catch(() => { sessionStorage.removeItem('margin-token') })
  }, [])
  useEffect(() => { const timer = setTimeout(() => refresh(search), 260); return () => clearTimeout(timer) }, [search, refresh])
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 4200); return () => clearTimeout(timer) }, [notice])

  function openWriter(post = null) {
    setActivePost(post)
    setForm(post ? { title: post.title, category: post.category, content: post.content } : { title: '', category: 'Field notes', content: '' })
    setModal('writer')
  }
  async function submitAuth(event) {
    event.preventDefault(); setBusy(true)
    try {
      const endpoint = authMode === 'login' ? '/auth/login' : '/auth/register'
      const result = await request(endpoint, { method: 'POST', body: JSON.stringify(authForm) })
      sessionStorage.setItem('margin-token', result.access_token); setUser(result.user); setModal(null); setAuthForm({ name: '', email: '', password: '' }); setNotice(`Welcome ${authMode === 'login' ? 'back' : 'to Margin'}, ${result.user.name}.`)
    } catch (error) { setNotice(error.message) } finally { setBusy(false) }
  }
  async function submitPost(event) {
    event.preventDefault(); setBusy(true)
    try {
      const path = activePost ? `/posts/${activePost.id}` : '/posts'
      await request(path, { method: activePost ? 'PUT' : 'POST', body: JSON.stringify(form) })
      setModal(null); setNotice(activePost ? 'Your story has been updated.' : 'Your story is now published.'); await refresh(search)
    } catch (error) { setNotice(error.message) } finally { setBusy(false) }
  }
  async function removePost(post) {
    if (!window.confirm(`Delete “${post.title}”? This cannot be undone.`)) return
    try { await request(`/posts/${post.id}`, { method: 'DELETE' }); setNotice('Story deleted.'); await refresh(search) }
    catch (error) { setNotice(error.message) }
  }
  function signOut() { sessionStorage.removeItem('margin-token'); setUser(null); setNotice('You have signed out.') }

  return <>
    <header className="topbar"><a className="brand" href="#top" aria-label="Margin home">margin<span>.</span></a><nav><a href="#stories">Stories</a><a href="#about">About</a></nav><div className="top-actions">{user ? <><span className="welcome">Hi, {user.name.split(' ')[0]}</span><button className="write-button" onClick={() => openWriter()}><Icon name="plus" size={16}/> Write</button><button className="signout" onClick={signOut}>Sign out</button></> : <button className="signin" onClick={() => { setAuthMode('login'); setModal('auth') }}>Sign in <Icon name="arrow" size={14}/></button>}</div></header>
    <main id="top"><section className="hero"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-dot"/> An independent publication</div><h1>Ideas worth<br/><em>the margin.</em></h1><p>A place for notes on making things for the web, learning out loud, and the details that make digital feel human.</p><a className="hero-link" href="#stories">Explore the stories <span>↓</span></a></div><div className="hero-art" aria-hidden="true"><div className="sun"/><div className="art-note"><span>VOL. 01 — EST. 2025</span><b>Think<br/>in the<br/><i>margins.</i></b><span className="art-line"/><small>COLLECTED THOUGHTS<br/>BY BHARATH B.</small></div><div className="orbit orbit-one"/><div className="orbit orbit-two"/><span className="art-cross cross-one">✳</span><span className="art-cross cross-two">✳</span><span className="art-index">01 / 05</span></div></section>
      <section id="stories" className="stories"><div className="section-heading"><div><div className="eyebrow muted">The reading room</div><h2>Latest stories<span>.</span></h2></div><label className="search-box"><Icon name="search" size={17}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search stories" aria-label="Search stories"/><kbd>⌕</kbd></label></div><div className="filter-row"><span>{search ? `Results for “${search}”` : 'A collection of thoughts, notes & learnings'}</span><span>{posts.length} {posts.length === 1 ? 'STORY' : 'STORIES'}</span></div>
        {loading ? <div className="empty-state"><div className="loader"/><p>Gathering the latest stories…</p></div> : posts.length === 0 ? <div className="empty-state"><div className="empty-mark"><Icon name="book" size={24}/></div><h3>{search ? 'No stories found' : 'The page is still blank.'}</h3><p>{search ? 'Try a different word or clear your search.' : 'Every good publication starts with a first sentence.'}</p>{user && !search && <button className="text-action" onClick={() => openWriter()}>Write the first story <span>↗</span></button>}</div> : <div className="post-grid">{posts.map((post, index) => <article className={`post-card ${index === 0 && !search ? 'featured' : ''}`} key={post.id}><div className={`post-art art-${index % 4}`} aria-hidden="true"><span className="art-category">{post.category}</span><span className="art-number">{String(index + 1).padStart(2, '0')}</span><div className="art-shape"/><span className="art-word">{index % 2 ? 'NOTES' : 'IDEAS'}</span></div><div className="post-meta"><span>{dateLabel(post.created_at)}</span><span>{readingTime(post.content)} MIN READ</span></div><h3>{post.title}</h3><p className="post-excerpt">{post.content.length > 190 ? `${post.content.slice(0, 190).trim()}…` : post.content}</p><div className="post-footer"><span className="author-dot">{post.author.name.slice(0, 1)}</span><span>By {post.author.name}</span><button className="read-link" onClick={() => { setActivePost(post); setModal('read') }}>Read story <Icon name="arrow" size={14}/></button></div>{user?.id === post.author.id && <div className="post-controls"><button title="Edit story" onClick={() => openWriter(post)}><Icon name="edit" size={15}/></button><button title="Delete story" onClick={() => removePost(post)}><Icon name="trash" size={15}/></button></div>}</article>)}</div>}
      </section><section id="about" className="about-strip"><div className="about-symbol">m.</div><div><div className="eyebrow muted">A note from the editor</div><p>“The best work leaves room for thought.<br/>That’s what we’re making here.”</p></div><div className="about-sign">Bharath B.<span>Founder & editor</span></div></section></main>
    <footer><a className="brand" href="#top">margin<span>.</span></a><span>Made with care, and room to think.</span><span>© {new Date().getFullYear()} BHARATH B.</span></footer>
    {notice && <div className="toast" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><Icon name="close" size={15}/></button></div>}
    {modal && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setModal(null) }}><section className={`modal ${modal === 'read' ? 'read-modal' : ''}`} role="dialog" aria-modal="true" aria-labelledby="modal-title"><button className="modal-close" onClick={() => setModal(null)} aria-label="Close"><Icon name="close"/></button>
      {modal === 'auth' && <><div className="eyebrow muted">{authMode === 'login' ? 'Welcome back' : 'Join the reading room'}</div><h2 id="modal-title">{authMode === 'login' ? 'Sign in.' : 'Create an account.'}</h2><p className="modal-intro">{authMode === 'login' ? 'Pick up where you left off.' : 'Create an account to write and publish your stories.'}</p><form onSubmit={submitAuth} className="form-stack">{authMode === 'register' && <label>Your name<input required minLength="2" maxLength="80" value={authForm.name} onChange={e => setAuthForm({...authForm, name: e.target.value})} placeholder="Bharath B."/></label>}<label>Email address<input type="email" required value={authForm.email} onChange={e => setAuthForm({...authForm, email: e.target.value})} placeholder="you@example.com"/></label><label>Password<input type="password" required minLength={authMode === 'register' ? 8 : 1} value={authForm.password} onChange={e => setAuthForm({...authForm, password: e.target.value})} placeholder={authMode === 'register' ? 'At least 8 characters' : 'Your password'}/></label><button className="primary-button" disabled={busy}>{busy ? 'One moment…' : authMode === 'login' ? 'Sign in' : 'Create account'} <span>↗</span></button></form><div className="switch-auth">{authMode === 'login' ? 'New to Margin?' : 'Already have an account?'} <button onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>{authMode === 'login' ? 'Create an account' : 'Sign in'}</button></div></>}
      {modal === 'writer' && <><div className="eyebrow muted">{activePost ? 'Shape the story' : 'Put it into words'}</div><h2 id="modal-title">{activePost ? 'Edit your story.' : 'Write a story.'}</h2><p className="modal-intro">Good things begin with a first draft.</p><form onSubmit={submitPost} className="form-stack"><label>Title<input required minLength="3" maxLength="160" value={form.title} onChange={e => setForm({...form, title: e.target.value})} placeholder="Give your story a title"/></label><label>Category<input required minLength="2" maxLength="50" value={form.category} onChange={e => setForm({...form, category: e.target.value})} placeholder="Field notes, Design, Process…"/></label><label>Your story<textarea required minLength="20" maxLength="20000" rows="9" value={form.content} onChange={e => setForm({...form, content: e.target.value})} placeholder="Start writing here…"/></label><button className="primary-button" disabled={busy}>{busy ? 'Saving…' : activePost ? 'Save changes' : 'Publish story'} <span>↗</span></button></form></>}
      {modal === 'read' && activePost && <><div className="eyebrow muted">{activePost.category} <span className="read-sep">/</span> {dateLabel(activePost.created_at)}</div><h2 id="modal-title" className="read-title">{activePost.title}</h2><div className="read-byline"><span className="author-dot">{activePost.author.name.slice(0, 1)}</span> By {activePost.author.name} <span>·</span> {readingTime(activePost.content)} min read</div><div className="read-content">{activePost.content.split(/\n\s*\n/).map((paragraph, i) => <p key={i}>{paragraph}</p>)}</div><button className="back-link" onClick={() => setModal(null)}><Icon name="back" size={16}/> Back to stories</button></>}
    </section></div>}
  </>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)
