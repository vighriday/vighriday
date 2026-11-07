/**
 * Serialize already-positioned font outlines without changing their geometry.
 * opentype.js 2.0.0's decimal formatter can emit NaN for near-integer floats.
 * Keep this separate from the font library's rounding and Y-axis conversion.
 */
export function serializePath(path) {
  const coordinates = {
    M: ['x', 'y'],
    L: ['x', 'y'],
    Q: ['x1', 'y1', 'x', 'y'],
    C: ['x1', 'y1', 'x2', 'y2', 'x', 'y'],
    Z: [],
  };
  return path.commands.map(command => {
    const keys = coordinates[command.type];
    if (!keys) throw new Error(`Unsupported outline command: ${command.type}`);
    const values = keys.map(key => {
      const value = command[key];
      if (!Number.isFinite(value)) throw new Error(`Invalid outline coordinate: ${key}`);
      return String(Number(value.toFixed(2)));
    });
    return command.type + values.join(' ');
  }).join('');
}
