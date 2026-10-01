import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioLines, Search, House, Library, Heart, ListMusic, Plus, ArrowUpRight, Play, Pause, SkipBack, SkipForward, Shuffle, Repeat, Volume2, VolumeX, Check, X, ChevronUp, ChevronDown, Trash2, Pencil, Music2, LoaderCircle, AlertCircle, Headphones, Disc3, Menu } from 'lucide-react';
import { request, duration, nextQueueIndex } from './api';

const EMPTY = { tracks: [], playlists: [], queue: [] };
const moods = [{ name: 'Slow mornings', query: 'morning acoustic indie music', label: 'TAKE YOUR TIME', className: 'morning', icon: '☀' }, { name: 'In the zone', query: 'instrumental focus jazz music', label: 'FIND YOUR FLOW', className: 'focus', icon: '◎' }, { name: 'After hours', query: 'late night chill electronic music', label: 'STAY A LITTLE LONGER', className: 'night', icon: '✦' }];
function stored(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } }
function save(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Private browsing can disable storage. */ } }
function Cover({ track, className = '' }) {
  return <div className={`cover ${className}`}><Music2 aria-hidden="true" />{track?.thumbnail && <img src={track.thumbnail} alt="" loading="lazy" onError={e => { e.currentTarget.style.display = 'none'; }} />}</div>;
}
function IconButton({ label, children, ...props }) { return <button type="button" className="icon-button" title={label} aria-label={label} {...props}>{children}</button>; }

export default function App() {
  const [state, setState] = useState(EMPTY);
  const [loaded, setLoaded] = useState(false);
  const [health, setHealth] = useState(null);
  const [page, setPage] = useState('home');
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [notice, setNotice] = useState(null);
  const [modal, setModal] = useState(null);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [currentId, setCurrentId] = useState(() => stored('cadence.current', null));
  const [currentEntry, setCurrentEntry] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [length, setLength] = useState(0);
  const [volume, setVolume] = useState(() => Math.max(0, Math.min(1, Number(stored('cadence.volume', 0.8)) || 0)));
  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState(false);
  const audio = useRef(null);
  const autoPlay = useRef(false);
  const selection = useRef(0);
  const searchAbort = useRef(null);
  const searchSequence = useRef(0);
  const modalRef = useRef(null);
  const current = state.tracks.find(t => t.id === currentId);
  const playlist = state.playlists.find(p => p.id === page);
  const downloads = state.tracks.filter(t => t.status === 'ready');
  const likes = state.tracks.filter(t => t.liked);
  const pending = state.tracks.filter(t => ['queued', 'downloading'].includes(t.status));
  const notify = useCallback((message, error = false) => setNotice({ message, error }), []);
  const refresh = useCallback(async () => { const data = await request('/state'); setState(data); setLoaded(true); return data; }, []);
  useEffect(() => { refresh().catch(e => notify(e.message, true)); request('/health').then(setHealth).catch(() => setHealth(null)); }, [refresh, notify]);
  useEffect(() => {
    const timer = setInterval(() => refresh().catch(() => {}), pending.length ? 1500 : 10000);
    return () => clearInterval(timer);
  }, [refresh, pending.length]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(null), 6000); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => { audio.current.volume = volume; save('cadence.volume', volume); }, [volume]);
  useEffect(() => { save('cadence.current', currentId); }, [currentId]);
  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement;
    const dialog = modalRef.current;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus(); };
  }, [modal]);
  const tryPlay = useCallback(() => {
    const promise = audio.current.play();
    promise?.catch(() => { autoPlay.current = false; notify('Your song is ready. Tap play to start listening.'); });
  }, [notify]);
  const source = current?.status === 'ready' ? `/api/audio/${current.id}` : undefined;
  useEffect(() => {
    const player = audio.current;
    setElapsed(0); setLength(0); setPlaying(false);
    if (source) { player.src = source; player.load(); if (autoPlay.current) tryPlay(); }
    else { player.pause(); player.removeAttribute('src'); player.load(); }
  }, [source, tryPlay]);
  useEffect(() => {
    if (!current || !('mediaSession' in navigator)) return;
    navigator.mediaSession.metadata = new MediaMetadata({ title: current.title, artist: current.artist, album: 'Cadence', artwork: [{ src: current.thumbnail, sizes: '480x360', type: 'image/jpeg' }] });
  }, [current]);
  async function mutate(path, method, body, message) {
    try { const data = await request(path, { method, body }); setState(data); if (message) notify(message); return data; }
    catch (e) { notify(e.message, true); throw e; }
  }
  function act(promise) { promise.catch(() => {}); }
  async function playTrack(track, entryId = null) {
    const token = ++selection.current;
    autoPlay.current = true;
    setCurrentEntry(entryId);
    if (track.id === currentId && current?.status === 'ready') { tryPlay(); return; }
    setCurrentId(track.id);
    setState(old => old.tracks.some(t => t.id === track.id) ? old : { ...old, tracks: [...old.tracks, { ...track, status: 'queued' }] });
    try {
      const song = await request('/downloads', { method: 'POST', body: track });
      if (token !== selection.current) return;
      setState(old => ({ ...old, tracks: [...old.tracks.filter(t => t.id !== song.id), song] }));
    } catch (e) {
      if (token === selection.current) { autoPlay.current = false; notify(e.message, true); refresh().catch(() => {}); }
    }
  }
  function togglePlay() {
    if (!current) return;
    if (playing) { autoPlay.current = false; audio.current.pause(); }
    else if (current.status === 'ready') { autoPlay.current = true; tryPlay(); }
    else if (!['queued', 'downloading'].includes(current.status)) act(playTrack(current, currentEntry));
  }
  function step(direction = 1, ended = false) {
    if (ended && repeat) { audio.current.currentTime = 0; tryPlay(); return; }
    if (direction < 0 && elapsed > 3) { audio.current.currentTime = 0; return; }
    const queue = state.queue;
    if (!queue.length) { autoPlay.current = false; return; }
    const index = queue.findIndex(e => e.id === currentEntry);
    if (ended && !shuffle && index === queue.length - 1) { autoPlay.current = false; return; }
    const next = direction < 0 ? (index <= 0 ? queue.length - 1 : index - 1) : nextQueueIndex(index, queue.length, shuffle);
    const entry = queue[next];
    const track = state.tracks.find(t => t.id === entry.track_id);
    if (track) act(playTrack(track, entry.id));
  }
  async function search(text) {
    const value = text.trim();
    if (!value) return;
    const token = ++searchSequence.current;
    searchAbort.current?.abort();
    const controller = new AbortController(); searchAbort.current = controller;
    setQuery(value); setSearched(value); setPage('search'); setSearching(true); setResults([]); setSearchError(''); setSidebar(false);
    try { const data = await request(`/search?q=${encodeURIComponent(value)}`, { signal: controller.signal }); if (token === searchSequence.current) setResults(data.tracks); }
    catch (e) { if (token === searchSequence.current && e.name !== 'AbortError') setSearchError(e.message); }
    finally { if (token === searchSequence.current) setSearching(false); }
  }
  function go(destination) { setPage(destination); setSidebar(false); }
  function createPlaylist() { setSidebar(false); setName(''); setModal({ type: 'create', track: modal?.type === 'add' ? modal.track : null }); }
  async function savePlaylist(event) {
    event.preventDefault(); setSaving(true);
    try {
      const data = await mutate(modal.type === 'rename' ? `/playlists/${modal.playlist.id}` : '/playlists', modal.type === 'rename' ? 'PATCH' : 'POST', { name: name.trim() });
      if (modal.type === 'create') {
        const created = data.playlists.at(-1);
        if (modal.track) await mutate(`/playlists/${created.id}/tracks`, 'POST', { track: modal.track });
        setPage(created.id);
      }
      setModal(null);
    } catch { /* Error is shown by mutate. */ } finally { setSaving(false); }
  }
  const enriched = tracks => tracks.map(t => ({ ...t, ...state.tracks.find(s => s.id === t.id) }));
  let list = page === 'search' ? enriched(results) : page === 'likes' ? likes : page === 'library' ? downloads : playlist ? playlist.track_ids.map(id => state.tracks.find(t => t.id === id)).filter(Boolean) : downloads.slice(0, 8);
  if (page === 'queue') list = state.queue.map(entry => ({ ...state.tracks.find(t => t.id === entry.track_id), entryId: entry.id }));
  function trackActions(track) {
    return <div className="track-actions">
      <IconButton label={`${track.liked ? 'Unlike' : 'Like'} ${track.title}`} aria-pressed={Boolean(track.liked)} onClick={() => act(mutate('/likes', 'POST', { track, liked: !track.liked }))}><Heart size={17} fill={track.liked ? 'currentColor' : 'none'} /></IconButton>
      <IconButton label={`Add ${track.title} to playlist`} onClick={() => setModal({ type: 'add', track })}><Plus size={18} /></IconButton>
      {page !== 'queue' && <IconButton label={`Add ${track.title} to queue`} onClick={() => act(mutate('/queue', 'POST', { track }, 'Added to your queue'))}><ListMusic size={18} /></IconButton>}
      {playlist && <IconButton label={`Remove ${track.title} from playlist`} onClick={() => act(mutate(`/playlists/${playlist.id}/tracks/${track.id}`, 'DELETE'))}><X size={17} /></IconButton>}
      {page === 'queue' && <><IconButton label={`Move ${track.title} up`} disabled={list[0]?.entryId === track.entryId} onClick={() => { const ids = state.queue.map(e => e.id); const i = ids.indexOf(track.entryId); [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]]; act(mutate('/queue', 'PUT', { ids })); }}><ChevronUp size={16} /></IconButton><IconButton label={`Move ${track.title} down`} disabled={list.at(-1)?.entryId === track.entryId} onClick={() => { const ids = state.queue.map(e => e.id); const i = ids.indexOf(track.entryId); [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]]; act(mutate('/queue', 'PUT', { ids })); }}><ChevronDown size={16} /></IconButton><IconButton label={`Remove ${track.title} from queue`} onClick={() => act(mutate(`/queue/${track.entryId}`, 'DELETE'))}><X size={17} /></IconButton></>}
    </div>;
  }
  const title = page === 'search' ? 'Find your next favorite.' : page === 'likes' ? 'Liked songs' : page === 'library' ? 'Your music, always here.' : page === 'queue' ? 'Up next' : playlist?.name || 'A little more rhythm.';
  return <div className="app-shell">
    {sidebar && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setSidebar(false)} />}
    <aside className={`sidebar ${sidebar ? 'open' : ''}`}>
      <a className="brand" href="#" onClick={e => { e.preventDefault(); go('home'); }}><span className="brand-icon"><AudioLines size={26} /></span>cadence<span className="brand-dot">.</span></a>
      <div className="nav-label">YOUR SPACE</div>
      <nav aria-label="Main navigation">{[{ id: 'home', name: 'Discover', icon: House }, { id: 'search', name: 'Search', icon: Search }, { id: 'library', name: 'Your library', icon: Library }, { id: 'likes', name: 'Liked songs', icon: Heart }, { id: 'queue', name: 'Play queue', icon: ListMusic }].map(({ id, name: label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => go(id)}><Icon size={19} /><span>{label}</span>{id === 'likes' && <small>{likes.length}</small>}{id === 'queue' && <small>{state.queue.length}</small>}</button>)}</nav>
      <div className="playlist-heading"><span className="nav-label">YOUR PLAYLISTS</span><IconButton label="Create playlist" onClick={createPlaylist}><Plus size={17} /></IconButton></div>
      <div className="playlist-nav">{state.playlists.map(p => <button key={p.id} className={`nav-item ${page === p.id ? 'active' : ''}`} onClick={() => go(p.id)}><span className="playlist-icon"><Music2 size={14} /></span><span>{p.name}</span></button>)}{!state.playlists.length && <button className="new-playlist" onClick={createPlaylist}><Plus size={16} /> Make room for a new mood</button>}</div>
      <div className="local-card"><span className="local-led" /><span>Your own little music corner<small>Saved locally. Played your way.</small></span></div>
      <div className="profile"><div className="avatar">Y</div><span>Your personal space<small>LOCAL LIBRARY</small></span><Headphones size={17} /></div>
    </aside>
    <main>
      <header className="topbar"><button className="mobile-menu icon-button" aria-label="Open navigation" onClick={() => setSidebar(true)}><Menu /></button><form className="searchbox" onSubmit={e => { e.preventDefault(); act(search(query)); }}><Search size={19} /><input aria-label="Search YouTube" value={query} onChange={e => setQuery(e.target.value)} maxLength={200} placeholder="Search songs, artists, or a feeling…" /><button type="submit" aria-label="Submit search"><span>Search</span><ArrowUpRight size={17} /></button></form><span className="connection"><span className={`local-led ${health ? '' : 'offline'}`} />{health ? 'YOUR MUSIC. LOCALLY.' : 'CONNECTING…'}</span></header>
      <div className="page-content">
        {!loaded && <div className="inline-status"><LoaderCircle className="spin" size={16} /> Connecting to your library… <button onClick={() => act(refresh().catch(e => { notify(e.message, true); throw e; }))}>Retry</button></div>}
        {health && (!health.yt_dlp || !health.ffmpeg) && <div className="error-panel"><AlertCircle size={20} />Install yt-dlp and ffmpeg on the Mac to enable downloads.</div>}
        <section className="page-heading"><div><span className="eyebrow">{playlist ? 'MADE BY YOU' : page === 'home' ? 'GOOD MUSIC, GOOD COMPANY' : 'YOUR PERSONAL SOUNDTRACK'}</span><h1>{title}</h1><p>{playlist ? `${list.length} songs · A collection that sounds like you` : page === 'search' ? 'All of YouTube. A space that feels like yours.' : page === 'likes' ? 'The ones you keep coming back to.' : page === 'library' ? `${downloads.length} downloaded songs, ready whenever you are.` : page === 'queue' ? `${list.length} songs lined up for your listening session.` : 'Find something you love. Make it part of your day.'}</p></div>{page === 'home' && <span className="edition">THE EVERYDAY MIX<br /><b>VOL. 001 ↗</b></span>}{playlist && <div className="heading-actions"><IconButton label="Rename playlist" onClick={() => { setName(playlist.name); setModal({ type: 'rename', playlist }); }}><Pencil size={18} /></IconButton><IconButton label="Delete playlist" onClick={() => setModal({ type: 'delete', playlist })}><Trash2 size={18} /></IconButton></div>}</section>
        {page === 'home' && <><section className="hero"><div className="hero-copy"><span className="eyebrow"><span className="tiny-star">✳</span> A SOUNDTRACK FOR RIGHT NOW</span><h2>Less noise.<br />More <em>music.</em></h2><p>Big discoveries. Old favorites.<br />A whole world of sound, in your own space.</p><button className="primary" onClick={() => act(search('indie soul chill music'))}><Play size={17} fill="currentColor" /> Find your sound <ArrowUpRight size={17} /></button></div><div className="record-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="vinyl"><div className="vinyl-label"><span>cadence</span><AudioLines size={33} /><small>SIDE A · GOOD FEELINGS</small><i /></div></div><div className="art-caption">SOUND GOOD.<br />FEEL GOOD.</div><span className="art-star">✳</span></div></section><section className="moods"><div className="section-heading"><h2>Set the mood</h2><span>A little inspiration to press play</span></div><div className="mood-grid">{moods.map(mood => <button className={`mood-card ${mood.className}`} key={mood.name} onClick={() => act(search(mood.query))}><span><small>{mood.label}</small><strong>{mood.name}</strong></span><span className="mood-art" aria-hidden="true">{mood.icon}</span><ArrowUpRight className="mood-arrow" size={20} /></button>)}</div></section></>}
        <section className="songs-section"><div className="section-heading"><h2>{page === 'home' ? 'On your rotation' : page === 'search' ? searched ? `Results for “${searched}”` : 'Start with a little curiosity' : page === 'queue' ? 'Your listening queue' : 'The collection'}{list.length > 0 && <small className="count">{list.length}</small>}</h2>{page === 'home' && <button className="text-button" onClick={() => go('library')}>View library <ArrowUpRight size={15} /></button>}{page === 'queue' && list.length > 0 && <button className="text-button" onClick={() => act(mutate('/queue', 'DELETE'))}>Clear queue</button>}{playlist && list.length > 0 && <button className="text-button" onClick={async () => { try { for (const track of list) await mutate('/queue', 'POST', { track }); notify('Playlist added to queue'); } catch { /* mutation displays error */ } }}>Queue all <ListMusic size={16} /></button>}</div>
          {searching && page === 'search' ? <div className="empty-state"><LoaderCircle className="spin" size={32} /><h3>Finding your sound…</h3><p>Searching YouTube for “{searched}”</p></div> : searchError && page === 'search' ? <div className="empty-state"><AlertCircle size={32} /><h3>That search hit a snag</h3><p>{searchError}</p><button className="secondary" onClick={() => act(search(searched))}>Try again</button></div> : !list.length ? <div className="empty-state"><div className="empty-icon">{page === 'likes' ? <Heart /> : page === 'queue' ? <ListMusic /> : page === 'search' ? <Search /> : <Disc3 />}</div><h3>{page === 'likes' ? 'Keep your favorites close' : page === 'queue' ? 'A good session starts with a song' : page === 'search' && searched ? 'No songs found' : playlist ? 'Every playlist starts somewhere' : page === 'search' ? 'What do you want to hear?' : 'Your next favorite is out there'}</h3><p>{page === 'likes' ? 'Tap the heart on any song to save it here.' : page === 'queue' ? 'Add songs with the queue button. Your order is saved automatically.' : playlist ? 'Find a song, tap +, and make this collection your own.' : page === 'search' && searched ? 'Try another song title or artist.' : 'Search for a song or choose a mood. Click a result to download and listen.'}</p>{page !== 'search' && <button className="secondary" onClick={() => { go('search'); document.querySelector('[aria-label="Search YouTube"]')?.focus(); }}>Discover music <ArrowUpRight size={16} /></button>}</div> : <div className="track-list"><div className="track-table-head"><span>#</span><span>SONG / ARTIST</span><span>TIME</span><span>MAKE IT YOURS</span></div>{list.map((track, index) => <article className={`track-row ${currentId === track.id ? 'selected' : ''}`} key={track.entryId || track.id}><button className="row-play" aria-label={`Play ${track.title}`} onClick={() => act(playTrack(track, track.entryId))}>{currentId === track.id && playing ? <AudioLines size={18} /> : <><span>{String(index + 1).padStart(2, '0')}</span><Play size={17} fill="currentColor" /></>}</button><button className="track-info" onClick={() => act(playTrack(track, track.entryId))}><Cover track={track} /><span><strong>{track.title}</strong><small>{track.artist}{track.status === 'ready' && <Check size={12} />}{['queued', 'downloading'].includes(track.status) && <span className="download-label"><LoaderCircle size={12} className="spin" /> {track.status}</span>}{track.status === 'error' && <span className="download-label failed">Download failed · click to retry</span>}</small></span></button><span className="track-duration">{duration(track.duration)}</span>{trackActions(track)}</article>)}</div>}
        </section><footer className="page-footer"><AudioLines size={15} /><span>A space for the music you love.</span><span>POWERED BY YOUR CURIOSITY</span></footer>
      </div>
    </main>
    <section className="player" aria-label="Music player"><div className="now-playing"><Cover track={current} /><div><strong>{current?.title || 'Your soundtrack starts here'}</strong><small>{current ? ['queued', 'downloading'].includes(current.status) ? 'Downloading to your library…' : current.status === 'error' ? 'Download failed. Tap retry.' : current.artist : 'Pick a song. Find your rhythm.'}</small></div>{current && <IconButton label={current.liked ? 'Unlike current song' : 'Like current song'} aria-pressed={Boolean(current.liked)} onClick={() => act(mutate('/likes', 'POST', { track: current, liked: !current.liked }))}><Heart size={18} fill={current.liked ? 'currentColor' : 'none'} /></IconButton>}</div><div className="playback"><div className="transport"><IconButton label="Shuffle" aria-pressed={shuffle} onClick={() => setShuffle(!shuffle)}><Shuffle size={17} /></IconButton><IconButton label="Previous song" disabled={!state.queue.length && elapsed <= 3} onClick={() => step(-1)}><SkipBack size={19} fill="currentColor" /></IconButton><button className="play-button" aria-label={playing ? 'Pause' : current?.status === 'error' ? 'Retry download' : 'Play'} disabled={!current || ['queued', 'downloading'].includes(current.status)} onClick={togglePlay}>{['queued', 'downloading'].includes(current?.status) ? <LoaderCircle className="spin" size={23} /> : playing ? <Pause size={22} fill="currentColor" /> : <Play size={22} fill="currentColor" />}</button><IconButton label="Next song" disabled={!state.queue.length} onClick={() => step()}><SkipForward size={19} fill="currentColor" /></IconButton><IconButton label="Repeat song" aria-pressed={repeat} onClick={() => setRepeat(!repeat)}><Repeat size={17} /></IconButton></div><div className="seek"><span>{duration(elapsed)}</span><input type="range" aria-label="Seek" min="0" max={length || 1} step="0.1" value={Math.min(elapsed, length || 1)} disabled={!source || !length} onChange={e => { audio.current.currentTime = Number(e.target.value); setElapsed(Number(e.target.value)); }} /><span>{duration(length || current?.duration || 0)}</span></div></div><div className="player-extras"><IconButton label="Show queue" onClick={() => go('queue')}><ListMusic size={20} /></IconButton><span className="player-divider" /><IconButton label={volume ? 'Mute' : 'Unmute'} onClick={() => setVolume(volume ? 0 : 0.8)}>{volume ? <Volume2 size={18} /> : <VolumeX size={18} />}</IconButton><input type="range" aria-label="Volume" min="0" max="1" step="0.01" value={volume} onChange={e => setVolume(Number(e.target.value))} /></div></section>
    <audio ref={audio} preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onTimeUpdate={() => setElapsed(audio.current.currentTime)} onDurationChange={() => setLength(Number.isFinite(audio.current.duration) ? audio.current.duration : 0)} onEnded={() => { setPlaying(false); step(1, true); }} onError={() => { if (source) notify('Audio could not be played. Check the server connection and try again.', true); }} />
    {current?.status === 'error' && <div className="download-error" role="alert"><AlertCircle size={16} /><span>{current.error}</span><button onClick={() => act(playTrack(current, currentEntry))}>Retry</button><IconButton label="Dismiss download error" onClick={() => setCurrentId(null)}><X size={15} /></IconButton></div>}
    {notice && <div className={`toast ${notice.error ? 'error' : ''}`} role={notice.error ? 'alert' : 'status'}>{notice.error ? <AlertCircle size={18} /> : <Check size={18} />}{notice.message}<IconButton label="Dismiss notification" onClick={() => setNotice(null)}><X size={16} /></IconButton></div>}
    {modal && <dialog ref={modalRef} className="modal" onCancel={() => setModal(null)} onClick={e => { if (e.target === modalRef.current) setModal(null); }}><div className="modal-heading"><h2>{modal.type === 'add' ? 'Find this song a home' : modal.type === 'delete' ? 'Delete playlist?' : modal.type === 'rename' ? 'A new name, same feeling' : 'Make it your own'}</h2><IconButton label="Close dialog" onClick={() => setModal(null)}><X size={20} /></IconButton></div>{modal.type === 'add' ? <><p>Add “{modal.track.title}” to a playlist.</p><div className="playlist-picker">{state.playlists.map(p => <button className="playlist-choice" key={p.id} disabled={p.track_ids.includes(modal.track.id)} onClick={() => act(mutate(`/playlists/${p.id}/tracks`, 'POST', { track: modal.track }, `Added to ${p.name}`).then(() => setModal(null)))}><Music2 size={19} /><span>{p.name}<small>{p.track_ids.length} songs</small></span>{p.track_ids.includes(modal.track.id) ? <Check size={18} /> : <Plus size={18} />}</button>)}</div>{!state.playlists.length && <p>You haven't created a playlist yet.</p>}<button className="secondary" onClick={createPlaylist}><Plus size={16} /> Create a playlist</button></> : modal.type === 'delete' ? <><p>Delete “{modal.playlist.name}”? Your songs and downloads will stay in your library.</p><button className="danger" onClick={() => act(mutate(`/playlists/${modal.playlist.id}`, 'DELETE').then(() => { setModal(null); go('home'); }))}>Delete playlist</button></> : <form onSubmit={savePlaylist}><p>A place for a mood, a moment, or your all-time favorites.</p><label htmlFor="playlist-name">Playlist name</label><input id="playlist-name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Sunday kind of love" maxLength={80} required autoFocus /><button className="primary" disabled={!name.trim() || saving}>{saving ? 'Saving…' : modal.type === 'rename' ? 'Save name' : 'Create playlist'}</button></form>}</dialog>}
  </div>;
}
