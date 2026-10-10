import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { AlertCircle } from 'lucide-react'

// Mock Data
const mockStops = [
  { id: 1, name: "Main Terminus", lat: 11.0168, lng: 76.9558, crowd: 4500, capacity: 2000 },
  { id: 2, name: "North Square", lat: 11.0268, lng: 76.9658, crowd: 200, capacity: 500 },
]

export function Maps() {
  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Interactive Resource Map</h1>
        <div className="flex gap-4 items-center">
          <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-2 rounded border border-red-200">
            <AlertCircle size={16} />
            <span>High Risk: Main Terminus (225% capacity)</span>
          </div>
        </div>
      </div>
      
      <div className="flex-1 bg-slate-100 rounded-lg overflow-hidden border border-slate-200">
        <MapContainer center={[11.0168, 76.9558]} zoom={13} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {mockStops.map((stop) => (
            <div key={stop.id}>
              <Circle
                center={[stop.lat, stop.lng]}
                radius={stop.crowd / 10}
                pathOptions={{
                  fillColor: stop.crowd > stop.capacity ? 'red' : 'green',
                  fillOpacity: 0.5,
                  color: stop.crowd > stop.capacity ? 'red' : 'green'
                }}
              />
              <Marker position={[stop.lat, stop.lng]}>
                <Popup>
                  <div className="font-bold">{stop.name}</div>
                  <div>Crowd: {stop.crowd}</div>
                  <div>Capacity: {stop.capacity}</div>
                </Popup>
              </Marker>
            </div>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
