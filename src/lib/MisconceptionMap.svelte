<script>
	import { onDestroy, onMount } from 'svelte';
	/** @type {any} */
	let maplibregl;

	/** @type {any[]} */
	export let features = [];
	/** @type {{ min: number; max: number }} */
	export let valueRange = { min: 0, max: 1 };
	export let metricLabel = '';
	export let yearLabel = '';

	/** @type {any} */
	let map;
	/** @type {any} */
	let mapContainer;
	let mapLoaded = false;
	/** @type {any} */
	let popup;

	const provinceLinesPath = '/geojson/province-state-lines.geojson';
	const populatedPlacesPath = '/geojson/populated-places-canada.geojson';

	/** @param {any[]} rows */
	function toGeoJson(rows) {
		return {
			type: 'FeatureCollection',
			features: rows.map((feature) => ({
				type: 'Feature',
				geometry: feature.geometry,
				properties: feature.properties
			}))
		};
	}

	/** @param {number} value */
	function formatValue(value) {
		if (!Number.isFinite(value)) return 'N/A';
		if (Math.abs(value) < 1) return `${(value * 100).toFixed(1)}%`;
		if (Math.abs(value) >= 1000) return value.toLocaleString();
		return value.toFixed(3);
	}

	/** @param {number} value */
	function formatSignedValue(value) {
		if (!Number.isFinite(value)) return 'N/A';
		const formatted = formatValue(Math.abs(value));
		return `${value > 0 ? '+' : value < 0 ? '-' : ''}${formatted}`;
	}

	/** @param {unknown} value */
	function escapeHtml(value) {
		return String(value ?? '').replace(/[&<>"']/g, (character) => {
			switch (character) {
				case '&':
					return '&amp;';
				case '<':
					return '&lt;';
				case '>':
					return '&gt;';
				case '"':
					return '&quot;';
				case "'":
					return '&#39;';
				default:
					return character;
			}
		});
	}

	/** @param {string} path @param {string} sourceId @param {string} layerId @param {string} layerType @param {() => void} addLayer */
	async function addGeoJsonLayer(path, sourceId, layerId, layerType, addLayer) {
		const response = await fetch(path);
		if (!response.ok) return false;
		const data = await response.json();
		map.addSource(sourceId, { type: 'geojson', data });
		addLayer();
		return true;
	}

	/** @param {any} event */
	function handleMetricPolygonClick(event) {
		if (!event.features?.length) return;
		const props = event.features[0].properties;
		if (popup) popup.remove();
		popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true })
			.setLngLat(event.lngLat)
			.setHTML(
				`<div style="font-family: 'Space Grotesk', sans-serif; font-size: 13px; line-height: 1.4; min-width: 220px;">
					<div style="font-weight: 700; margin-bottom: 4px;">${escapeHtml(props.region)}</div>
					<div style="margin-bottom: 6px; color: #475569;">${escapeHtml(props.province)}</div>
					<div style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: #64748b;">${escapeHtml(metricLabel)} (${escapeHtml(yearLabel)})</div>
					<div style="margin-top: 8px; font-weight: 700; font-size: 15px;">Value: ${formatValue(Number(props.value))}</div>
					<div style="margin-top: 4px; color: #0f172a;">Province: ${formatValue(Number(props.provinceValue))}</div>
					<div style="margin-top: 4px; color: #0f172a;">Compared to province: ${formatSignedValue(Number(props.diffFromProvince))} (${Number.isFinite(Number(props.ratioToProvince)) ? `${Number(props.ratioToProvince).toFixed(2)}x province` : 'N/A'})</div>
				</div>`
			)
			.addTo(map);
	}

	function updateData() {
		if (!mapLoaded || !map) return;
		const source = map.getSource('metric-polygons');
		const geojson = toGeoJson(features);
		if (source) {
			source.setData(geojson);
		}
	}

	function updatePaint() {
		if (!mapLoaded || !map) return;
		const min = Number.isFinite(valueRange?.min) ? valueRange.min : 0;
		const max = Number.isFinite(valueRange?.max) ? valueRange.max : 1;
		const safeMax = Math.max(min + 0.0001, max);
		map.setPaintProperty('metric-polygons-fill', 'fill-color', [
			'interpolate',
			['linear'],
			['get', 'value'],
			min,
			'#f7fbff',
			(min + safeMax) / 2,
			'#6baed6',
			safeMax,
			'#08306b'
		]);
		map.setPaintProperty('metric-polygons-fill', 'fill-opacity', 0.82);
	}

	$: if (mapLoaded) {
		updateData();
		updatePaint();
	}

	onMount(async () => {
		const m = await import('maplibre-gl');
		maplibregl = m?.default ?? m;
		await import('maplibre-gl/dist/maplibre-gl.css');

		map = new maplibregl.Map({
			container: mapContainer,
			style: 'https://tiles.openfreemap.org/styles/positron',
			center: [-95, 56],
			zoom: 3.5,
			minZoom: 2,
			maxZoom: 12,
			pitch: 0,
			bearing: 0,
			scrollZoom: true,
			attributionControl: false
		});

		map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'bottom-left');

		map.on('load', async () => {
				map.addSource('metric-polygons', { type: 'geojson', data: toGeoJson(features) });

				map.addLayer({
					id: 'metric-polygons-fill',
					type: 'fill',
					source: 'metric-polygons',
					paint: {
						'fill-color': '#f7fbff',
						'fill-opacity': 0.82
					}
				});

				map.addLayer({
					id: 'metric-polygons-outline',
					type: 'line',
					source: 'metric-polygons',
					paint: {
						'line-color': 'rgba(15, 23, 42, 0.45)',
						'line-width': 0.7,
						'line-opacity': 0.7
					}
				});

			try {
				await addGeoJsonLayer(provinceLinesPath, 'province-state-lines', 'province-state-lines', 'line', () => {
					map.addLayer({
						id: 'province-state-lines',
						type: 'line',
						source: 'province-state-lines',
						paint: {
							'line-color': '#6b7280',
							'line-width': 1.1,
							'line-opacity': 0.45
						}
					});
				});
				console.info('Loaded province-state lines');
			} catch (err) {
				console.warn('Province-state lines unavailable:', /** @type {any} */ (err)?.message ?? err);
			}

			try {
				await addGeoJsonLayer(populatedPlacesPath, 'populated-places', 'populated-places', 'circle', () => {
					map.addLayer({
						id: 'populated-places-label',
						type: 'symbol',
						source: 'populated-places',
						minzoom: 4.5,
						layout: {
							'text-field': ['get', 'name'],
							'text-size': ['interpolate', ['linear'], ['zoom'], 4.5, 10, 8, 12],
							'text-offset': [0, 0.85],
							'text-anchor': 'top',
							'text-allow-overlap': false,
							'text-font': ['Open Sans Semibold', 'Arial Unicode MS Bold']
						},
						paint: {
							'text-color': '#1f2937',
							'text-halo-color': '#ffffff',
							'text-halo-width': 1.2
						}
					});
				});
				console.info('Loaded populated places');
			} catch (err) {
				console.warn('Populated places unavailable:', /** @type {any} */ (err)?.message ?? err);
			}

			updatePaint();

			map.on('click', 'metric-polygons-fill', handleMetricPolygonClick);

			map.on('mouseenter', 'metric-polygons-fill', () => {
				map.getCanvas().style.cursor = 'pointer';
			});
			map.on('mouseleave', 'metric-polygons-fill', () => {
				map.getCanvas().style.cursor = '';
			});

			mapLoaded = true;
		});

		map.on('style.load', () => {
			map.setProjection({ type: map.getZoom() < 7 ? 'globe' : 'mercator' });
			map.on('zoom', () => {
				map.setProjection({ type: map.getZoom() < 7 ? 'globe' : 'mercator' });
			});
		});
	});

	onDestroy(() => {
		if (popup) popup.remove();
		if (map) map.remove();
		popup = null;
		map = null;
	});
</script>

<div class="map-wrapper">
	<div class="map" bind:this={mapContainer}></div>
</div>

<style>
	.map-wrapper {
		position: relative;
		width: 100%;
		height: 62vh;
		min-height: 460px;
		border-radius: 18px;
		overflow: hidden;
		box-shadow: 0 16px 40px rgba(0, 0, 0, 0.12);
	}

	.map {
		width: 100%;
		height: 100%;
	}

	:global(.maplibregl-popup-content) {
		border-radius: 12px;
		box-shadow: 0 10px 28px rgba(0, 0, 0, 0.2);
	}

	:global(.maplibregl-ctrl-bottom-left) {
		margin: 16px;
	}
</style>
