import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { readFullStations } from 'db-hafas-stations'

const here = dirname(fileURLToPath(import.meta.url))
const output = resolve(here, '../../data/german-stops.json')

function modeFor(station) {
  const products = station.products ?? {}
  if (products.nationalExpress || products.national || products.regionalExpress || products.regional || products.suburban) {
    return 'train'
  }
  if (products.tram) return 'tram'
  if (products.subway) return 'subway'
  if (products.bus) return 'bus'
  if (products.ferry) return 'ferry'
  return null
}

const stops = []
const seen = new Set()

for await (const station of readFullStations()) {
  const location = station.location
  if (!location || typeof location.latitude !== 'number' || typeof location.longitude !== 'number') continue
  const lat = location.latitude
  const lon = location.longitude
  if (lat < 47.2 || lat > 55.2 || lon < 5.5 || lon > 15.2) continue
  if (!station.name || seen.has(station.id)) continue
  seen.add(station.id)
  stops.push({
    id: String(station.id),
    name: String(station.name),
    latitude: lat,
    longitude: lon,
    type: 'STOP',
    mode: modeFor(station),
  })
}

mkdirSync(dirname(output), { recursive: true })
writeFileSync(output, JSON.stringify(stops), 'utf8')
console.log(`Wrote ${stops.length} stops to ${output}`)
