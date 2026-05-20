/**
 * zoom-engine.ts — Compute CSS transform to zoom/pan into a screen region.
 *
 * Given a region [x_frac, y_frac, w_frac, h_frac] of a container,
 * computes the scale and translate needed to bring that region into focus.
 */

export interface ZoomTransform {
  scale: number;
  translateX: number; // percent
  translateY: number; // percent
}

/**
 * Compute zoom transform to fill the container with the given region.
 * region: [x_frac, y_frac, w_frac, h_frac] — all 0–1 fractions of container
 * padding: extra space around the region (0.05 = 5% padding)
 */
export function computeZoom(
  region: [number, number, number, number],
  padding = 0.05
): ZoomTransform {
  const [rx, ry, rw, rh] = region;

  // Add padding
  const padX = rw * padding;
  const padY = rh * padding;
  const px = Math.max(0, rx - padX);
  const py = Math.max(0, ry - padY);
  const pw = Math.min(1 - px, rw + 2 * padX);
  const ph = Math.min(1 - py, rh + 2 * padY);

  // Scale to fill container — use minimum scale so region fits
  const scale = Math.min(1 / pw, 1 / ph, 3.0); // cap at 3x zoom

  // Center the region in view
  const regionCenterX = px + pw / 2;
  const regionCenterY = py + ph / 2;

  // Translate to bring region center to container center
  // After scale, container center is at 50%, region center is at regionCenter*scale
  const translateX = (0.5 - regionCenterX * scale) * 100;
  const translateY = (0.5 - regionCenterY * scale) * 100;

  return { scale, translateX, translateY };
}

/**
 * Interpolate between identity transform and a zoom transform.
 * progress: 0 = no zoom, 1 = full zoom
 */
export function interpolateZoom(
  target: ZoomTransform,
  progress: number
): ZoomTransform {
  const p = Math.min(1, Math.max(0, progress));
  return {
    scale:      1 + (target.scale - 1) * p,
    translateX: target.translateX * p,
    translateY: target.translateY * p,
  };
}

/** Convert ZoomTransform to CSS transform string. */
export function zoomToCss(z: ZoomTransform): string {
  return `scale(${z.scale}) translate(${z.translateX}%, ${z.translateY}%)`;
}
