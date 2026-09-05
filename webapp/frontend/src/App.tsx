import { Anchor, AppShell, Group, Title } from "@mantine/core";
import { NavLink, Route, Routes } from "react-router-dom";

import CriteriaPage from "./pages/CriteriaPage";
import JobDetailPage from "./pages/JobDetailPage";
import JobsPage from "./pages/JobsPage";

function App() {
  return (
    <AppShell header={{ height: 56 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" gap="xl">
          <Title order={4}>LinkedIn Job Tracker</Title>
          <Group gap="md">
            <Anchor component={NavLink} to="/" end>
              Jobs
            </Anchor>
            <Anchor component={NavLink} to="/criteria">
              Criteria
            </Anchor>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route path="/criteria" element={<CriteriaPage />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}

export default App;
