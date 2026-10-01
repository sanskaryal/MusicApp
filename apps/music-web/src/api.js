export async function request(path, { method = 'GET', body, signal } = {}) {
  const response = await fetch(`/api${path}`, { method, signal, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  let data;
  try { data = await response.json(); } catch { throw new Error('The music server is unavailable. Check that it is running.'); }
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}
export function duration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}
export function nextQueueIndex(index, length, shuffle, random = Math.random) {
  if (!length) return -1;
  if (!shuffle || length === 1) return (index + 1) % length;
  const alternatives = Array.from({ length }, (_, i) => i).filter(i => i !== index);
  return alternatives[Math.floor(random() * alternatives.length)];
}
