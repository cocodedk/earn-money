import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./app/Layout";
import { ROUTES } from "./app/routes";
import { ProjectsList } from "./features/projects/ProjectsList";
import { CreateProject } from "./features/projects/CreateProject";
import { TargetsList } from "./features/targets/TargetsList";
import { CreateTarget } from "./features/targets/CreateTarget";
import { StubsList } from "./features/stubs/StubsList";
import { StubDetail } from "./features/stubs/StubDetail";
import { ScanRunsList } from "./features/scan-runs/ScanRunsList";
import { CreateScanRun } from "./features/scan-runs/CreateScanRun";
import { ComingSoon } from "./features/coming-soon";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to={ROUTES.projects} replace />} />
        <Route path={ROUTES.projects} element={<ProjectsList />} />
        <Route path={ROUTES.projectsNew} element={<CreateProject />} />
        <Route path={ROUTES.targets} element={<TargetsList />} />
        <Route path={ROUTES.targetsNew} element={<CreateTarget />} />
        <Route path={ROUTES.stubs} element={<StubsList />} />
        <Route path={ROUTES.stubDetail} element={<StubDetail />} />
        <Route path={ROUTES.scanRuns} element={<ScanRunsList />} />
        <Route path={ROUTES.scanRunsNew} element={<CreateScanRun />} />
        <Route
          path={ROUTES.scanRunDetail}
          element={<ComingSoon name="Scan Run Detail" />}
        />
        <Route path={ROUTES.findings} element={<ComingSoon name="Findings" />} />
        <Route path={ROUTES.evidence} element={<ComingSoon name="Evidence" />} />
        <Route path={ROUTES.settings} element={<ComingSoon name="Settings" />} />
        <Route path="*" element={<ComingSoon name="Not found" />} />
      </Route>
    </Routes>
  );
}
