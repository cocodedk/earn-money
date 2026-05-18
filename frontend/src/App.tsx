import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ROUTES } from "./app/routes";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { ComingSoon } from "./features/coming-soon";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to={ROUTES.projects} replace />} />
        <Route path={ROUTES.projects} element={<ProjectsList />} />
        <Route path={ROUTES.projectsNew} element={<CreateProject />} />
        <Route path={ROUTES.targets} element={<ComingSoon name="Targets" />} />
        <Route path={ROUTES.stubs} element={<ComingSoon name="Stubs" />} />
        <Route path={ROUTES.scanRuns} element={<ComingSoon name="Scan Runs" />} />
        <Route path={ROUTES.findings} element={<ComingSoon name="Findings" />} />
        <Route path={ROUTES.evidence} element={<ComingSoon name="Evidence" />} />
        <Route path={ROUTES.settings} element={<ComingSoon name="Settings" />} />
        <Route path="*" element={<ComingSoon name="Not found" />} />
      </Route>
    </Routes>
  );
}
