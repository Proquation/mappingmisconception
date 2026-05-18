<script>
	import { onDestroy, onMount } from 'svelte';
	let maplibregl;

	export let features = [];
	export let valueRange = { min: 0, max: 1 };
	export let metricLabel = '';
	export let metricVector = '';
	export let yearLabel = '';

	let map;
	let mapContainer;
	let mapLoaded = false;
	let popup;

	const boundaryBasePath = '/geojson/csd_enriched_simplified';
	const provinceLinesPath = '/geojson/province-state-lines.geojson';
	const populatedPlacesPath = '';

	let lastSelectionKey = '';

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

	function formatValue(value) {
		if (!Number.isFinite(value)) return 'N/A';
		if (Math.abs(value) < 1) return `${(value * 100).toFixed(1)}%`;
		if (Math.abs(value) >= 1000) return value.toLocaleString();
		return value.toFixed(3);
	}

	function getBoundaryPath(extension) {
		return `${boundaryBasePath}.${extension}`;
	}

	async function addGeoJsonLayer(path, sourceId, layerId, layerType, addLayer) {
		const response = await fetch(path);
		if (!response.ok) return false;
		const data = await response.json();
		map.addSource(sourceId, { type: 'geojson', data });
		addLayer();
		return true;
	}

	function updatePolygonPaint() {
		if (!mapLoaded || !map) return;
		if (!map.getLayer('metric-fill')) return;
		const min = Number.isFinite(valueRange?.min) ? valueRange.min : 0;
		const max = Number.isFinite(valueRange?.max) ? valueRange.max : 1;
		const safeMax = Math.max(min + 0.0001, max);
		map.setPaintProperty('metric-fill', 'fill-color', [
			'interpolate',
			['linear'],
			['coalesce', ['get', 'value'], min],
			min,
			'#f7fbff',
			(min + safeMax) / 2,
			'#6baed6',
			safeMax,
			'#08306b'
		]);
	}

	function updatePolygonData() {
		if (!mapLoaded || !map) return;
		const source = map.getSource('metric-polygons');
		if (!source) return;
		source.setData(toGeoJson(features));
		console.info('Map polygons updated:', features.length);
	}

	$: if (mapLoaded) {
		updatePolygonData();
		updatePolygonPaint();
		const selectionKey = `${metricVector}|${yearLabel}`;
		if (selectionKey !== lastSelectionKey) {
			if (popup) popup.remove();
			lastSelectionKey = selectionKey;
		}
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
			attributionControl: false,
			projection: 'globe'
		});

		map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'bottom-left');

		map.on('load', async () => {
			console.info('Map loaded');
			map.addSource('metric-polygons', { type: 'geojson', data: toGeoJson(features) });

			map.addLayer({
				id: 'metric-fill',
				type: 'fill',
				source: 'metric-polygons',
				paint: { 'fill-color': '#e0e0e0', 'fill-opacity': 0.72 }
			});

			map.addLayer({
				id: 'metric-outline',
				type: 'line',
				source: 'metric-polygons',
				paint: { 'line-color': '#8a97a6', 'line-width': 0.6, 'line-opacity': 0.65 }
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
				console.warn('Province-state lines unavailable:', err?.message ?? err);
			}

			// Populated places disabled.

			updatePolygonData();
			updatePolygonPaint();

			map.on('click', 'metric-fill', (event) => {
				if (!event.features?.length) return;
				const props = event.features[0].properties;
				const region = props?.region || 'Unknown';
				const province = props?.province || '';
				if (popup) popup.remove();
				popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true })
					.setLngLat(event.lngLat)
					.setHTML(
						`<div style="font-family: 'Space Grotesk', sans-serif; font-size: 13px; line-height: 1.4;">
							<div style="font-weight: 600; margin-bottom: 4px;">${region}</div>
							<div>${province}</div>
							<div>${metricLabel} (${yearLabel})</div>
							<div style="margin-top: 4px; font-weight: 600;">${formatValue(Number(props?.value))}</div>
						</div>`
					)
					.addTo(map);
			});

			map.on('mouseenter', 'metric-fill', () => {
				map.getCanvas().style.cursor = 'pointer';
			});
			map.on('mouseleave', 'metric-fill', () => {
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
