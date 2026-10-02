// Inspect shortcut metadata in memory. Never send executable paths or arguments.
export function shortcutHints(exe = '', args = ''): { platform?: string; platformSource?: string; excluded?: boolean } {
  const command = `${exe} ${args}`.toLowerCase().replace(/\\/g, '/');
  if (/\b(es-de|emulationstation|nested.?desktop)\b/.test(command)) return {excluded: true};
  const folders: Record<string, string> = {ps2: 'PlayStation 2', psx: 'PlayStation', ps3: 'PlayStation 3',
    psp: 'PlayStation Portable', gba: 'Game Boy Advance', gbc: 'Game Boy Color', gb: 'Game Boy',
    gc: 'Nintendo GameCube', gamecube: 'Nintendo GameCube', wii: 'Wii', wiiu: 'Wii U',
    n64: 'Nintendo 64', snes: 'Super Nintendo', nes: 'NES', nds: 'Nintendo DS', n3ds: 'Nintendo 3DS',
    dreamcast: 'Dreamcast', saturn: 'Sega Saturn', genesis: 'Sega Mega Drive/Genesis'};
  const matches = Array.from(command.matchAll(/\/roms\/([a-z0-9]+)\//g)).map(m => folders[m[1]]).filter(Boolean);
  const platforms = new Set(matches);
  const pcsx2 = /\bpcsx2(?:-qt)?(?:\.sh|\.appimage|\.exe)?\b/.test(command);
  if (pcsx2 && platforms.size && !platforms.has('PlayStation 2')) return {platformSource: 'Conflicting shortcut hints'};
  if (platforms.size > 1) return {platformSource: 'Conflicting shortcut hints'};
  if (platforms.size === 1) return {platform: [...platforms][0], platformSource: 'ROM folder'};
  if (pcsx2) {
    if (/\.(iso|chd|cso|bin|elf)(?:["'\s]|$)/i.test(command)) return {platform: 'PlayStation 2', platformSource: 'PCSX2'};
    return {excluded: true}; // An emulator UI is not a directly launched game.
  }
  return {};
}
