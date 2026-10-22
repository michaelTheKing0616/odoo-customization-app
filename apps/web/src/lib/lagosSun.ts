/** Touch 119: sunrise and sunset for Lagos (6.45 N, 3.39 E), NOAA approximation, in UTC minutes. */
const LAT = 6.4541;
const LON = 3.3947;

function dayOfYear(d: Date): number {
  return Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 86_400_000);
}

export function lagosSunUtcMinutes(d: Date): { sunrise: number; sunset: number } {
  const g = ((2 * Math.PI) / 365) * (dayOfYear(d) - 1);
  const eqt = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g) - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const lat = (LAT * Math.PI) / 180;
  const ha = (Math.acos(Math.cos((90.833 * Math.PI) / 180) / (Math.cos(lat) * Math.cos(decl)) - Math.tan(lat) * Math.tan(decl)) * 180) / Math.PI;
  return { sunrise: 720 - 4 * (LON + ha) - eqt, sunset: 720 - 4 * (LON - ha) - eqt };
}

/** True between Lagos sunset and the next sunrise. */
export function isLagosNight(now: Date = new Date()): boolean {
  const { sunrise, sunset } = lagosSunUtcMinutes(now);
  const m = now.getUTCHours() * 60 + now.getUTCMinutes();
  return m >= sunset || m < sunrise;
}
