import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import App from './App';
import { duration, nextQueueIndex, request } from './api';
const song = { id: 'abcdefghijk', title: 'Ocean lights', artist: 'Test artist', duration: 123, thumbnail: '', status: 'idle', liked: 0 };
function mockServer() {
  let state = { tracks: [], queue: [], playlists: [] };
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (path, options = {}) => {
    let data = state;
    const body = options.body ? JSON.parse(options.body) : {};
    if (path === '/api/health') data = { status: 'ok', yt_dlp: true, ffmpeg: true };
    if (path.startsWith('/api/search')) data = { tracks: [song] };
    if (path === '/api/likes') { state = { ...state, tracks: [{ ...song, liked: body.liked ? 1 : 0 }] }; data = state; }
    if (path === '/api/queue' && options.method === 'POST') { state = { ...state, tracks: state.tracks.length ? state.tracks : [song], queue: [...state.queue, { id: 'entry1', track_id: song.id }] }; data = state; }
    if (path === '/api/playlists' && options.method === 'POST') { state = { ...state, playlists: [{ id: 'playlist1', name: body.name, track_ids: [] }] }; data = state; }
    if (path === '/api/downloads') { data = { ...song, status: 'downloading' }; state = { ...state, tracks: [data] }; }
    return { ok: true, json: async () => data };
  });
}
async function searchSong() { fireEvent.change(screen.getByLabelText('Search YouTube'), { target: { value: 'Ocean' } }); fireEvent.click(screen.getByLabelText('Submit search')); await screen.findByRole('button', { name: 'Play Ocean lights' }); }
describe('player helpers', () => {
  it('formats durations safely', () => { expect(duration(125)).toBe('2:05'); expect(duration(NaN)).toBe('0:00'); });
  it('advances and shuffles without repeating the same queue entry', () => { expect(nextQueueIndex(2, 3, false)).toBe(0); expect(nextQueueIndex(1, 3, true, () => 0)).toBe(0); expect(nextQueueIndex(0, 0, false)).toBe(-1); });
  it('surfaces server error messages', async () => { vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, json: async () => ({ error: 'Search timed out' }) }); await expect(request('/search')).rejects.toThrow('Search timed out'); });
});
describe('music app', () => {
  it('searches, likes and queues a song', async () => {
    const fetch = mockServer(); render(<App />); await screen.findByText('YOUR MUSIC. LOCALLY.'); await searchSong();
    fireEvent.click(screen.getByLabelText('Like Ocean lights'));
    await screen.findByLabelText('Unlike Ocean lights');
    fireEvent.click(screen.getByLabelText('Add Ocean lights to queue'));
    await screen.findByText('Added to your queue');
    expect(fetch).toHaveBeenCalledWith('/api/queue', expect.objectContaining({ method: 'POST' }));
    fireEvent.click(screen.getByRole('button', { name: /Play queue/ }));
    expect(screen.getByRole('heading', { name: 'Up next' })).toBeInTheDocument();
    expect(screen.getByLabelText('Remove Ocean lights from queue')).toBeInTheDocument();
  });
  it('starts a download when a result is clicked', async () => {
    const fetch = mockServer(); render(<App />); await searchSong(); fireEvent.click(screen.getByLabelText('Play Ocean lights'));
    await screen.findByText('Downloading to your library…');
    expect(fetch).toHaveBeenCalledWith('/api/downloads', expect.objectContaining({ method: 'POST', body: expect.stringContaining(song.id) }));
    expect(screen.getByRole('button', { name: 'Play', exact: true })).toBeDisabled();
  });
  it('creates a playlist with a dialog', async () => {
    mockServer(); render(<App />); await screen.findByText('YOUR MUSIC. LOCALLY.');
    fireEvent.click(screen.getByLabelText('Create playlist')); fireEvent.change(screen.getByLabelText('Playlist name'), { target: { value: 'Night drive' } });
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Create playlist', exact: true }));
    await screen.findByRole('heading', { name: 'Night drive' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
  it('shows a retry action for failed search', async () => {
    const fetch = mockServer(); render(<App />); await screen.findByText('YOUR MUSIC. LOCALLY.');
    fetch.mockImplementation(async path => ({ ok: !path.startsWith('/api/search'), json: async () => path.startsWith('/api/search') ? { error: 'YouTube is unavailable' } : { tracks: [], queue: [], playlists: [] } }));
    fireEvent.change(screen.getByLabelText('Search YouTube'), { target: { value: 'Ocean' } }); fireEvent.click(screen.getByLabelText('Submit search'));
    await waitFor(() => expect(screen.getByText('YouTube is unavailable')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });
});
