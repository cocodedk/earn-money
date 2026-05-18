import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { ComingSoon } from "./features/coming-soon";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsList />} />
        <Route path="/projects/new" element={<CreateProject />} />
        <Route path="/targets" element={<ComingSoon name="Targets" />} />
        <Route path="/stubs" element={<ComingSoon name="Stubs" />} />
        <Route path="/scan-runs" element={<ComingSoon name="Scan Runs" />} />
        <Route path="/findings" element={<ComingSoon name="Findings" />} />
        <Route path="/evidence" element={<ComingSoon name="Evidence" />} />
        <Route path="/settings" element={<ComingSoon name="Settings" />} />
        <Route path="*" element={<ComingSoon name="Not found" />} />
      </Route>
    </Routes>
  );
}
