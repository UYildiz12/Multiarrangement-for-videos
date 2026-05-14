export function getExperimentArenaSize(width: number, height: number, stimulusCount: number): number {
  const denseTrial = stimulusCount > 24;
  const verticalReserve = denseTrial ? 150 : 120;
  const horizontalReserve = denseTrial ? 96 : 110;
  const maxSize = denseTrial ? 760 : 640;
  const minSize = denseTrial ? 280 : 260;
  const available = Math.min(width - horizontalReserve, height - verticalReserve);
  return Math.max(minSize, Math.min(maxSize, Math.floor(available)));
}
