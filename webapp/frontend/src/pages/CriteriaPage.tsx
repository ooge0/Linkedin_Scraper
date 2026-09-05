import { useEffect, useState } from "react";
import {
  ActionIcon,
  Alert,
  Button,
  Checkbox,
  Group,
  Loader,
  NumberInput,
  Paper,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconTrash } from "@tabler/icons-react";

import { ResizableTh } from "../components/ResizableTh";
import { useColumnWidths } from "../hooks/useColumnWidths";
import { api, ApiError } from "../api/client";
import type { Criterion } from "../api/types";

const INITIAL_WIDTHS = { term: 240, weight: 120, enabled: 100, actions: 60 };

export default function CriteriaPage() {
  const { widths, startResize } = useColumnWidths(INITIAL_WIDTHS);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);

  const [newTerm, setNewTerm] = useState("");
  const [newWeight, setNewWeight] = useState<number | "">(1);
  const [adding, setAdding] = useState(false);

  function loadCriteria() {
    setLoading(true);
    setError(null);
    api
      .listCriteria()
      .then(setCriteria)
      .catch(() => setError("Failed to load criteria"))
      .finally(() => setLoading(false));
  }

  useEffect(loadCriteria, []);

  async function handleAdd() {
    if (!newTerm.trim()) return;
    setAdding(true);
    try {
      const created = await api.addCriterion({
        term: newTerm.trim(),
        weight: newWeight === "" ? 1 : newWeight,
      });
      setCriteria((current) => [...current, created]);
      setNewTerm("");
      setNewWeight(1);
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Add failed",
        message: err instanceof ApiError ? err.message : "Could not add criterion",
      });
    } finally {
      setAdding(false);
    }
  }

  async function handleWeightChange(id: number, weight: number) {
    try {
      const updated = await api.updateCriterion(id, { weight });
      setCriteria((current) => current.map((c) => (c.id === id ? updated : c)));
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Update failed",
        message: err instanceof ApiError ? err.message : "Could not update weight",
      });
    }
  }

  async function handleEnabledChange(id: number, enabled: boolean) {
    try {
      const updated = await api.updateCriterion(id, { enabled });
      setCriteria((current) => current.map((c) => (c.id === id ? updated : c)));
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Update failed",
        message: err instanceof ApiError ? err.message : "Could not update criterion",
      });
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.deleteCriterion(id);
      setCriteria((current) => current.filter((c) => c.id !== id));
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Delete failed",
        message: err instanceof ApiError ? err.message : "Could not delete criterion",
      });
    }
  }

  async function handleRecalculate() {
    setRecalculating(true);
    try {
      const result = await api.recalculateScores();
      notifications.show({
        color: "green",
        title: "Scores recalculated",
        message: `Updated ${result.updated} job(s)`,
      });
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Recalculate failed",
        message: err instanceof ApiError ? err.message : "Could not recalculate scores",
      });
    } finally {
      setRecalculating(false);
    }
  }

  return (
    <Stack gap="md" maw={800}>
      <Group justify="space-between">
        <Title order={2}>Match-scoring criteria</Title>
        <Button onClick={handleRecalculate} loading={recalculating} variant="light">
          Recalculate scores
        </Button>
      </Group>
      <Text c="dimmed" size="sm">
        A job's match score is the sum of every enabled criterion's weight
        whose term appears in its title, description, or skills, normalized
        to 0-100. Negative weights act as a penalty. Changing criteria here
        doesn't update existing scores by itself -- click "Recalculate
        scores" afterwards.
      </Text>

      <Paper withBorder p="md">
        <Group align="flex-end">
          <TextInput
            label="Term"
            placeholder="e.g. python"
            value={newTerm}
            onChange={(event) => setNewTerm(event.currentTarget.value)}
            w={240}
          />
          <NumberInput
            label="Weight"
            value={newWeight}
            onChange={(value) => setNewWeight(value === "" ? "" : Number(value))}
            w={120}
          />
          <Button onClick={handleAdd} loading={adding} disabled={!newTerm.trim()}>
            Add criterion
          </Button>
        </Group>
      </Paper>

      {error && (
        <Alert color="red" title="Error">
          {error}
        </Alert>
      )}

      <Paper withBorder>
        <Table.ScrollContainer
          minWidth={widths.term + widths.weight + widths.enabled + widths.actions}
        >
          <Table striped highlightOnHover style={{ tableLayout: "fixed" }}>
            <Table.Thead>
              <Table.Tr>
                <ResizableTh width={widths.term} onResizeStart={(x) => startResize("term", x)}>
                  Term
                </ResizableTh>
                <ResizableTh width={widths.weight} onResizeStart={(x) => startResize("weight", x)}>
                  Weight
                </ResizableTh>
                <ResizableTh
                  width={widths.enabled}
                  onResizeStart={(x) => startResize("enabled", x)}
                >
                  Enabled
                </ResizableTh>
                <ResizableTh
                  width={widths.actions}
                  onResizeStart={(x) => startResize("actions", x)}
                >
                  {""}
                </ResizableTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {criteria.map((criterion) => (
                <Table.Tr key={criterion.id}>
                  <Table.Td style={{ width: widths.term }}>{criterion.term}</Table.Td>
                  <Table.Td style={{ width: widths.weight }}>
                    <NumberInput
                      value={criterion.weight}
                      onChange={(value) =>
                        value !== "" && handleWeightChange(criterion.id, Number(value))
                      }
                      w={100}
                    />
                  </Table.Td>
                  <Table.Td style={{ width: widths.enabled }}>
                    <Checkbox
                      checked={criterion.enabled}
                      onChange={(event) =>
                        handleEnabledChange(criterion.id, event.currentTarget.checked)
                      }
                    />
                  </Table.Td>
                  <Table.Td style={{ width: widths.actions }}>
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      onClick={() => handleDelete(criterion.id)}
                      title="Delete criterion"
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>

        {loading && (
          <Group justify="center" p="md">
            <Loader size="sm" />
          </Group>
        )}

        {!loading && criteria.length === 0 && !error && (
          <Text c="dimmed" ta="center" p="md">
            No criteria yet -- add one above.
          </Text>
        )}
      </Paper>
    </Stack>
  );
}
