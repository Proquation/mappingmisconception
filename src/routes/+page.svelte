<script>
	import { onMount } from 'svelte';
	import { csvParse } from 'd3-dsv';
	import { base } from '$app/paths';
	import MisconceptionMap from '$lib/MisconceptionMap.svelte';
	import '$lib/assets/global-styles.css';

	const yearOptions = [2016, 2021];
	const enrichedGeoJsonPath = () => `${base}/geojson/csd_enriched_simplified.geojson`;

	let isLoading = true;
	let loadError = '';
	let selectedYear = 2021;
	let metricOptions = [];
	let selectedMetricVector = '';
	let selectedMetric = null;
	let rawRows = [];
	let polygonFeatures = [];
	let features = [];
	let valueRange = { min: 0, max: 1 };
	let provinceSummary = {
		count: 0,
		average: null,
		highest: null,
		lowest: null,
		items: []
	};

	const FORMAT_OVERRIDES = {
		// --- Gini index (0–1 index, not a percent) ---
		'v_CA16_1142': 'index',
		'v_CA21_1142': 'index',

		// --- Adjusted income decile (1–10 ordinal) ---
		'v_CA16_1100': 'index',
		'v_CA21_1100': 'index',

		// --- True percentages (label explicitly says %) ---
		'v_CA16_1040': 'percent',   // Prevalence of LIM-AT (%)
		'v_CA21_1040': 'percent',

		// --- Dollar values ---
		'v_CA16_560':  'currency',  // Median total income ($)
		'v_CA21_560':  'currency',
		'v_CA16_566':  'currency',  // Median after-tax income ($)
		'v_CA21_566':  'currency',
		'v_CA16_4311': 'currency',  // Median dwelling value ($)
		'v_CA21_4311': 'currency',

		// --- Raw counts (everything else defaults to 'number') ---
		// v_CA16_1010 / v_CA21_1010  — LIM low-income status (count)
		// v_CA16_4263 / v_CA21_4263  — Dwellings by construction period (count)
		// v_CA16_4272 / v_CA21_4272  — Dwellings by condition (count)
		// v_CA16_4288 / v_CA21_4288  — Households by shelter-cost ratio (count)
		// v_CA16_4305 / v_CA21_4305  — Owner households (count)
		// v_CA16_4313 / v_CA21_4313  — Tenant households (count)
		// v_CA16_4404 / v_CA21_4404  — Immigrant status total (count)
		// v_CA16_4410 / v_CA21_4410  — Immigrants (count)
		// v_CA16_4437 / v_CA21_4437  — Age at immigration (count)
		// v_CA16_4875 / v_CA21_4875  — Visible minority total (count)
		// v_CA16_4878–4899 / v_CA21_4878–4899 — Specific visible minority groups (count)
		// v_CA16_1189 / v_CA21_1189  — Non-official languages (count)
		// v_CA16_1192 / v_CA21_1192  — Indigenous languages (count)
		// v_CA16_5847 / v_CA21_5847  — Bachelor's degree or higher (count)
		// v_CA16_6087 / v_CA21_6087  — Military science field (count)
		// v_CA16_6582 / v_CA21_6582  — Occupation category (count)
	};

	function normalizeMetricOptions(rows) {
		const metricMap = new Map();
		rows.forEach((row) => {
			if (!row.vector || !row.label) return;
			if (!metricMap.has(row.vector)) {
				const format = FORMAT_OVERRIDES[row.vector] ?? (row.label?.toLowerCase().includes('%') ? 'percent' : 'number');
				metricMap.set(row.vector, { label: row.label, format });
			}
		});
		return Array.from(metricMap.entries()).map(([vector, { label, format }]) => ({ vector, label, format }));
	}

	function parseMetricRow(row) {
		const value = Number(row.csd_value);
		const provinceValue = Number(row.province_value);
		const diffFromProvince = Number(row.diff_from_province);
		const ratioToProvince = Number(row.ratio_to_province);
		return {
			geoid: String(row.GeoUID || '').trim(),
			region: String(row['Region Name'] || '').trim(),
			province: String(row.province_name || '').trim(),
			vector: String(row.vector || '').trim(),
			label: String(row.label || '').trim(),
			value: Number.isFinite(value) ? value : null,
			provinceValue: Number.isFinite(provinceValue) ? provinceValue : null,
			diffFromProvince: Number.isFinite(diffFromProvince) ? diffFromProvince : null,
			ratioToProvince: Number.isFinite(ratioToProvince) ? ratioToProvince : null
		};
	}

	function formatValue(value, format = 'number') {
		if (!Number.isFinite(value)) return 'N/A';
		switch (format) {
			case 'percent':
				return `${(value * 100).toFixed(1)}%`;
			case 'index':
				return value.toFixed(3);
			case 'currency':
				return `$${Math.round(value).toLocaleString()}`;
			default:
				return value >= 1000 ? Math.round(value).toLocaleString() : value.toFixed(3);
		}
	}

	// function normalizePolygonFeature(feature) {
	// 	const properties = feature?.properties ?? {};
	// 	const value = Number(properties.csd_value);
	// 	const provinceValue = Number(properties.province_value);
	// 	const diffFromProvince = Number(properties.diff_from_province);
	// 	const ratioToProvince = Number(properties.ratio_to_province);

	// 	return {
	// 		type: 'Feature',
	// 		geometry: feature?.geometry ?? null,
	// 		properties: {
	// 			geoid: String(properties.GeoUID || properties.GEOUID || properties.CSDUID || '').trim(),
	// 			region: String(properties['Region Name'] || properties.CSDNAME || '').trim(),
	// 			province: String(properties.province_name || '').trim(),
	// 			vector: String(properties.vector || '').trim(),
	// 			label: String(properties.label || '').trim(),
	// 			value: Number.isFinite(value) ? value : null,
	// 			provinceValue: Number.isFinite(provinceValue) ? provinceValue : null,
	// 			diffFromProvince: Number.isFinite(diffFromProvince) ? diffFromProvince : null,
	// 			ratioToProvince: Number.isFinite(ratioToProvince) ? ratioToProvince : null
	// 		}
	// 	};
	// }

	function normalizePolygonFeature(feature) {
		const properties = feature?.properties ?? {};
		return {
			type: 'Feature',
			geometry: feature?.geometry ?? null,
			properties  // keep ALL raw properties as-is
		};
	}

	async function loadPolygonFeatures() {
		console.info('Loading polygon GeoJSON...');
		const response = await fetch(enrichedGeoJsonPath());
		if (!response.ok) {
			throw new Error('Missing polygon file: csd_enriched_simplified.geojson');
		}
		const geojson = await response.json();
		console.info('Polygon GeoJSON loaded:', geojson?.features?.length ?? 0, 'features');
		return (geojson.features || []).map(normalizePolygonFeature).filter((feature) => feature.geometry);
	}

	async function loadYearData(year) {
		isLoading = true;
		loadError = '';
		try {
			console.info('Loading CSV for year:', year);
			const csvResponse = await fetch(`${base}/csd_vs_province_${year}.csv`);
			if (!csvResponse.ok) throw new Error(`Failed to load csd_vs_province_${year}.csv`);

			// Only load polygons once
			if (!polygonFeatures.length) {
				polygonFeatures = await loadPolygonFeatures();
			}

			const csv = await csvResponse.text();
			rawRows = csvParse(csv).map(parseMetricRow).filter((r) => r.geoid && r.vector);
			console.info('CSV rows loaded:', rawRows.length);
			metricOptions = normalizeMetricOptions(rawRows);
			console.info('Metric options:', metricOptions.length);
			if (!metricOptions.find((o) => o.vector === selectedMetricVector)) {
				selectedMetricVector = metricOptions[0]?.vector ?? '';
			}
		} catch (error) {
			console.error('Error loading data:', error);
			loadError = error?.message || 'Unable to load data.';
		} finally {
			isLoading = false;
		}
	}

	function buildFeatures() {
		if (!selectedMetricVector) {
			features = [];
			valueRange = { min: 0, max: 1 };
			return;
		}

		console.info('Building features for:', {
			year: selectedYear,
			metric: selectedMetricVector,
			polygons: polygonFeatures.length
		});

		const mapped = polygonFeatures
			.map((feature) => {
				const p = feature.properties;
				// columns in the GeoJSON are like csd_value_2021, province_value_2021, etc.
				const value = Number(p[`csd_value_${selectedYear}`]);
				const provinceValue = Number(p[`province_value_${selectedYear}`]);
				const diffFromProvince = Number(p[`diff_from_province_${selectedYear}`]);
				const ratioToProvince = Number(p[`ratio_to_province_${selectedYear}`]);
				const vector = String(p[`vector_${selectedYear}`] ?? '').trim();
				const label = String(p[`label_${selectedYear}`] ?? '').trim();

				if (vector !== selectedMetricVector) return null;
				if (!Number.isFinite(value)) return null;

				return {
					type: 'Feature',
					geometry: feature.geometry,
					properties: {
						geoid: String(p.CSDUID || p.GeoUID || '').trim(),
						region: String(p.CSDNAME || p['Region Name'] || '').trim(),
						province: String(p[`province_name_${selectedYear}`] ?? '').trim(),
						vector,
						label,
						value,
						provinceValue: Number.isFinite(provinceValue) ? provinceValue : null,
						diffFromProvince: Number.isFinite(diffFromProvince) ? diffFromProvince : null,
						ratioToProvince: Number.isFinite(ratioToProvince) ? ratioToProvince : null
					}
				};
			})
			.filter(Boolean);

		const values = mapped.map((f) => f.properties.value);
		features = mapped;
		valueRange = { min: Math.min(...values), max: Math.max(...values) };
		console.info('Value range updated:', valueRange, 'features:', mapped.length);
	}

	function buildProvinceSummary() {
		if (!selectedMetricVector) {
			provinceSummary = {
				count: 0,
				average: null,
				highest: null,
				lowest: null,
				items: []
			};
			return;
		}

		const provinceGroups = new Map();
		rawRows
			.filter((row) => row.vector === selectedMetricVector && row.province)
			.forEach((row) => {
				if (!provinceGroups.has(row.province)) {
					provinceGroups.set(row.province, []);
				}
				provinceGroups.get(row.province).push(row);
			});

		const provinces = Array.from(provinceGroups.entries())
			.map(([province, rows]) => {
				const provinceValue = rows.find((row) => Number.isFinite(row.provinceValue))?.provinceValue ?? null;
				const values = rows.map((row) => row.value).filter(Number.isFinite);
				const diffs = rows.map((row) => row.diffFromProvince).filter(Number.isFinite);
				const ratios = rows.map((row) => row.ratioToProvince).filter(Number.isFinite);

				return {
					province,
					provinceValue,
					csdCount: rows.length,
					averageValue: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null,
					averageDifference: diffs.length ? diffs.reduce((sum, value) => sum + value, 0) / diffs.length : null,
					averageRatio: ratios.length ? ratios.reduce((sum, value) => sum + value, 0) / ratios.length : null
				};
			})
			.filter((province) => Number.isFinite(province.provinceValue));

		provinces.sort((left, right) => right.provinceValue - left.provinceValue);
		const provinceValues = provinces.map((province) => province.provinceValue).filter(Number.isFinite);

		provinceSummary = {
			count: provinces.length,
			average: provinceValues.length
				? provinceValues.reduce((sum, value) => sum + value, 0) / provinceValues.length
				: null,
			highest: provinces[0] ?? null,
			lowest: provinces[provinces.length - 1] ?? null,
			items: provinces.slice(0, 6)
		};
	}

	function handleYearChange(event) {
		selectedYear = Number(event.target.value);
		loadYearData(selectedYear);
	}

	$: selectedMetric = metricOptions.find((option) => option.vector === selectedMetricVector) ?? null;
	$: if (rawRows.length && polygonFeatures.length && selectedMetricVector) {
		console.info('Reactive rebuild:', {
			year: selectedYear,
			metric: selectedMetricVector,
			rows: rawRows.length,
			polygons: polygonFeatures.length
		});
		buildFeatures();
		buildProvinceSummary();
	}

	$: if (selectedMetricVector) {
		console.info('Selected metric changed:', selectedMetricVector);
	}

	$: if (selectedYear) {
		console.info('Selected year changed:', selectedYear);
	}
	$: if (!selectedMetricVector && metricOptions.length) {
		selectedMetricVector = metricOptions[0].vector;
	}

	onMount(async () => {
		try {
			await loadYearData(selectedYear);
		} catch (error) {
			console.error('Error loading polygons:', error);
			loadError = error?.message || 'Unable to load polygon data.';
			isLoading = false;
		}
	});
</script>

<main class="page">
	<div class="text">
		<h1>Mapping Misconception</h1>
		<p>
			Explore demographic metrics across Canadian census subdivisions. Choose a year and metric to see
			where values concentrate.
		</p>
	</div>

	{#if isLoading}
		<div class="status">Loading misconception data...</div>
	{:else if loadError}
		<div class="status error">{loadError}</div>
	{:else}
		<div class="text" style="margin-bottom: 0px;">
			<h3>Filter the map</h3>
			<div class="filter-row">
				<div class="filter-group">
					<span class="filter-label">Year</span>
					<select class="select-input" on:change={handleYearChange} bind:value={selectedYear}>
						{#each yearOptions as year}
							<option value={year}>{year}</option>
						{/each}
					</select>
				</div>

				<div class="filter-group" style="min-width: 320px;">
					<span class="filter-label">Metric</span>
					<select class="select-input" bind:value={selectedMetricVector}>
						{#each metricOptions as option}
							<option value={option.vector}>{option.label}</option>
						{/each}
					</select>
				</div>
			</div>

			<div class="legend-panel">
				<div class="legend-title-row">
					<div>
						<span class="filter-label">Colour scale</span>
						<div class="legend-title">{selectedMetric?.label ?? 'Metric'}</div>
					</div>
					<div class="legend-meta">{selectedYear}</div>
				</div>
				<div class="legend">
					<span class="legend-swatch"></span>
					<span>{formatValue(valueRange.min)}</span>
					<span>to</span>
					<span>{formatValue(valueRange.max)}</span>
				</div>
			</div>

			<div class="summary-panel">
				<div class="summary-header">
					<div>
						<span class="filter-label">Province values</span>
						<div class="summary-title">Selected metric benchmark</div>
					</div>
					<div class="summary-meta">{provinceSummary.count} provinces</div>
				</div>
				<div class="summary-stats">
					<div class="summary-stat">
						<span>Highest</span>
						<strong>{provinceSummary.highest?.province ?? 'N/A'}</strong>
						<em>{formatValue(provinceSummary.highest?.provinceValue)}</em>
					</div>
					<div class="summary-stat">
						<span>Lowest</span>
						<strong>{provinceSummary.lowest?.province ?? 'N/A'}</strong>
						<em>{formatValue(provinceSummary.lowest?.provinceValue)}</em>
					</div>
					<div class="summary-stat">
						<span>Average</span>
						<strong>{formatValue(provinceSummary.average)}</strong>
						<em>across provinces</em>
					</div>
				</div>
				<div class="summary-list">
					{#each provinceSummary.items as province}
						<div class="summary-item">
							<div>
								<strong>{province.province}</strong>
								<span>{province.csdCount} CSDs</span>
							</div>
							<div class="summary-item-value">{formatValue(province.provinceValue)}</div>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<section class="map-block">
			<MisconceptionMap
				features={features}
				valueRange={valueRange}
				metricLabel={selectedMetric?.label ?? ''}
				metricVector={selectedMetricVector}
				yearLabel={String(selectedYear)}
			/>
		</section>
	{/if}
</main>

<style>
	.legend-panel,
	.summary-panel {
		margin-top: 16px;
		padding: 16px 18px;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.92);
		box-shadow: 0 12px 28px rgba(0, 0, 0, 0.06);
	}

	.legend-title-row,
	.summary-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 12px;
	}

	.legend-title,
	.summary-title {
		font-size: 18px;
		font-weight: 600;
		margin-top: 4px;
	}

	.legend-meta,
	.summary-meta,
	.summary-stat span,
	.summary-item span {
		font-size: 13px;
		color: var(--brandGray70);
	}

	.legend-swatch {
		height: 12px;
		width: 140px;
		border-radius: 999px;
		background: linear-gradient(90deg, #f7fbff, #6baed6, #08306b);
		box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
	}

	.summary-stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 12px;
		margin-bottom: 14px;
	}

	.summary-stat {
		padding: 12px;
		border-radius: 12px;
		background: rgba(30, 55, 101, 0.04);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.summary-stat strong {
		font-size: 15px;
	}

	.summary-stat em {
		font-style: normal;
		font-size: 13px;
		color: var(--brandGray70);
	}

	.summary-list {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
		gap: 10px;
	}

	.summary-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 10px 12px;
		border-radius: 12px;
		background: rgba(0, 0, 0, 0.03);
	}

	.summary-item strong {
		display: block;
		font-size: 14px;
	}

	.summary-item-value {
		font-weight: 600;
		white-space: nowrap;
	}

	.map-block {
		padding: 0 20px;
	}
</style>
