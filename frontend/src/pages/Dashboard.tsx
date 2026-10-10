import { Activity, AlertTriangle, Users } from "lucide-react"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

const mockData = [
  { time: "08:00", actual: 400, predicted: 420 },
  { time: "09:00", actual: 800, predicted: 850 },
  { time: "10:00", actual: 1200, predicted: 1100 },
  { time: "11:00", actual: 1500, predicted: 1600 },
  { time: "12:00", actual: 2100, predicted: 2300 },
  { time: "13:00", actual: 2500, predicted: 2400 },
]

export function Dashboard() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">District Overview</h1>
      
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-slate-500">Current Crowd</h3>
            <Users className="text-blue-500" size={24} />
          </div>
          <div className="text-3xl font-bold">4,520</div>
          <div className="text-sm text-slate-500 mt-2">+12% from expected</div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-slate-500">Available Buses</h3>
            <Activity className="text-green-500" size={24} />
          </div>
          <div className="text-3xl font-bold">42 / 50</div>
          <div className="text-sm text-slate-500 mt-2">8 buses in maintenance</div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200 border-l-4 border-l-red-500">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-red-600">Active Alerts</h3>
            <AlertTriangle className="text-red-500" size={24} />
          </div>
          <div className="text-3xl font-bold">2</div>
          <div className="text-sm text-slate-500 mt-2">High demand predicted at Main Stop</div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
        <h3 className="font-medium text-lg mb-6">Passenger Demand Forecast vs Actual</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={mockData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="time" axisLine={false} tickLine={false} />
              <YAxis axisLine={false} tickLine={false} />
              <Tooltip cursor={{fill: '#f1f5f9'}} />
              <Bar dataKey="actual" fill="#94a3b8" radius={[4, 4, 0, 0]} name="Actual Demand" />
              <Bar dataKey="predicted" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Predicted Demand" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
