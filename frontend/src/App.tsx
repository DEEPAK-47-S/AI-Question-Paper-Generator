import { Routes, Route } from "react-router-dom"
import { Layout } from "./components/layout/Layout"
import { Dashboard } from "./pages/Dashboard"
import { Maps } from "./pages/Maps"

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="maps" element={<Maps />} />
        {/* We will add more routes here for Phase 4 */}
      </Route>
    </Routes>
  )
}

export default App
