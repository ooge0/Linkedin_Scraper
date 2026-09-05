import { useEffect, useState, type CSSProperties, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  NumberInput,
  Paper,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Tooltip,
  Pagination as MantinePagination,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconExternalLink, IconPlayerTrackNext, IconTrash } from "@tabler/icons-react";

import { HEADER_ROW_HEIGHT, ResizableTh } from "../components/ResizableTh";
import { useColumnWidths } from "../hooks/useColumnWidths";
import { useLocalStorageState } from "../hooks/useLocalStorageState";
import { api, ApiError } from "../api/client";
import { APPLICATION_STATUSES, type ApplicationStatus, type Job } from "../api/types";

const PAGE_SIZE_OPTIONS = ["10", "20", "50", "100"];
const TABLE_MAX_HEIGHT = "65vh";

// "posted" is free text off LinkedIn ("3 days ago", "2 months ago", ...),
// not a real date -- this heuristic is deliberately coarse (month/year
// units = stale) rather than parsing exact ages, since the point is just
// to visually flag likely-dead listings, not compute a precise cutoff.
function isStalePosted(posted: string): boolean {
  return /\b(month|months|year|years)\b/i.test(posted);
}

type ColumnKey =
  | "scraped_at"
  | "title"
  | "company"
  | "location"
  | "posted"
  | "salary"
  | "employment_type"
  | "seniority"
  | "applicants"
  | "match_score"
  | "job_id"
  | "search_location"
  | "notes"
  | "status";

interface ColumnDef {
  key: ColumnKey;
  label: string;
  sortKey?: string;
  width: number;
  filter: "text" | "status" | "score" | "none";
}

// Order: scan columns (what/where/when/how-well) first, technical/
// reference columns (job id, which search found it) next, then the
// user's own tracking fields (notes, status) last. This is only the
// *default* order -- columns can be dragged into any order, which is
// persisted per-browser (see DEFAULT_COLUMN_ORDER below).
const COLUMN_DEFS: Record<ColumnKey, ColumnDef> = {
  scraped_at: { key: "scraped_at", label: "Scraped", sortKey: "scraped_at", width: 100, filter: "none" },
  title: { key: "title", label: "Title", sortKey: "title", width: 260, filter: "text" },
  company: { key: "company", label: "Company", sortKey: "company", width: 160, filter: "text" },
  location: { key: "location", label: "Location", width: 140, filter: "text" },
  posted: { key: "posted", label: "Posted", sortKey: "posted", width: 110, filter: "text" },
  salary: { key: "salary", label: "Salary", width: 130, filter: "text" },
  employment_type: { key: "employment_type", label: "Employment Type", width: 150, filter: "text" },
  seniority: { key: "seniority", label: "Seniority", width: 130, filter: "text" },
  applicants: { key: "applicants", label: "Applicants", width: 110, filter: "text" },
  match_score: { key: "match_score", label: "Score", sortKey: "match_score", width: 80, filter: "score" },
  job_id: { key: "job_id", label: "Job ID", width: 110, filter: "text" },
  search_location: { key: "search_location", label: "Search Location", width: 140, filter: "text" },
  notes: { key: "notes", label: "Notes", width: 200, filter: "text" },
  status: { key: "status", label: "Status", width: 160, filter: "status" },
};

const DEFAULT_COLUMN_ORDER: ColumnKey[] = [
  "scraped_at",
  "title",
  "company",
  "location",
  "posted",
  "salary",
  "employment_type",
  "seniority",
  "applicants",
  "match_score",
  "job_id",
  "search_location",
  "notes",
  "status",
];

const INITIAL_WIDTHS = Object.fromEntries(
  Object.values(COLUMN_DEFS).map((c) => [c.key, c.width]),
);

interface TextFilters {
  title: string;
  company: string;
  location: string;
  posted: string;
  salary: string;
  employment_type: string;
  seniority: string;
  applicants: string;
  job_id: string;
  search_location: string;
  notes: string;
}

const EMPTY_TEXT_FILTERS: TextFilters = {
  title: "",
  company: "",
  location: "",
  posted: "",
  salary: "",
  employment_type: "",
  seniority: "",
  applicants: "",
  job_id: "",
  search_location: "",
  notes: "",
};

// A preset captures the filter/sort state only -- not layout (column
// order/width already persist automatically per-browser, see the
// useLocalStorageState call below), since layout isn't something a user
// switches back and forth between the way they switch views like
// "unreviewed, best match first" vs "applied".
interface FilterPreset {
  name: string;
  status: ApplicationStatus | null;
  minScore: number | "";
  textFilters: TextFilters;
  sortBy: string;
  sortDir: "ASC" | "DESC";
}

export default function JobsPage() {
  const navigate = useNavigate();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [findingNext, setFindingNext] = useState(false);

  const [status, setStatus] = useState<ApplicationStatus | null>(null);
  const [minScore, setMinScore] = useState<number | "">("");
  const [textFilters, setTextFilters] = useState<TextFilters>(EMPTY_TEXT_FILTERS);
  const [debouncedTextFilters] = useDebouncedValue(textFilters, 400);

  // Default to best-match-first rather than newest-first, so the jobs
  // worth acting on are what's on screen without configuring sort every
  // session -- see docs/roadmap.rst for the reasoning.
  const [sortBy, setSortBy] = useState("match_score");
  const [sortDir, setSortDir] = useState<"ASC" | "DESC">("DESC");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const { widths, startResize } = useColumnWidths(INITIAL_WIDTHS, "jobs-table-column-widths");
  const [columnOrder, setColumnOrder] = useLocalStorageState(
    "jobs-table-column-order",
    DEFAULT_COLUMN_ORDER,
  );
  const [draggedKey, setDraggedKey] = useState<ColumnKey | null>(null);

  const [presets, setPresets] = useLocalStorageState<FilterPreset[]>("jobs-filter-presets", []);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [newPresetName, setNewPresetName] = useState("");

  function setTextFilter(key: keyof TextFilters, value: string) {
    setTextFilters((current) => ({ ...current, [key]: value }));
    // A manual filter edit means whatever's on screen no longer
    // necessarily matches the loaded preset -- clear the selection so
    // the presets dropdown doesn't keep showing a name next to filters
    // it no longer describes, and so reselecting that same preset later
    // is a real value change the Select will actually notify us about
    // (selecting an option that already equals its current value is a
    // no-op as far as onChange is concerned).
    setSelectedPreset(null);
  }

  function applyPreset(name: string | null) {
    setSelectedPreset(name);
    const preset = presets.find((p) => p.name === name);
    if (!preset) return;
    setStatus(preset.status);
    setMinScore(preset.minScore);
    setTextFilters(preset.textFilters);
    setSortBy(preset.sortBy);
    setSortDir(preset.sortDir);
  }

  function handleSavePreset() {
    const name = newPresetName.trim();
    if (!name) return;
    const preset: FilterPreset = { name, status, minScore, textFilters, sortBy, sortDir };
    // Saving under a name that already exists overwrites it -- simpler
    // than a separate "rename"/"overwrite?" flow for what's a small,
    // low-stakes list of shortcuts.
    setPresets([...presets.filter((p) => p.name !== name), preset]);
    setSelectedPreset(name);
    setNewPresetName("");
  }

  function handleDeletePreset() {
    if (!selectedPreset) return;
    setPresets(presets.filter((p) => p.name !== selectedPreset));
    setSelectedPreset(null);
  }

  function handleDrop(targetKey: ColumnKey) {
    if (!draggedKey || draggedKey === targetKey) {
      setDraggedKey(null);
      return;
    }
    const next = [...columnOrder];
    const fromIndex = next.indexOf(draggedKey);
    const toIndex = next.indexOf(targetKey);
    next.splice(fromIndex, 1);
    next.splice(toIndex, 0, draggedKey);
    setColumnOrder(next);
    setDraggedKey(null);
  }

  useEffect(() => {
    setPage(1);
  }, [status, minScore, debouncedTextFilters, sortBy, sortDir, pageSize]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    api
      .listJobs({
        status: status ?? undefined,
        min_score: minScore === "" ? undefined : minScore,
        title: debouncedTextFilters.title || undefined,
        company: debouncedTextFilters.company || undefined,
        location: debouncedTextFilters.location || undefined,
        posted: debouncedTextFilters.posted || undefined,
        salary: debouncedTextFilters.salary || undefined,
        employment_type: debouncedTextFilters.employment_type || undefined,
        seniority: debouncedTextFilters.seniority || undefined,
        applicants: debouncedTextFilters.applicants || undefined,
        job_id: debouncedTextFilters.job_id || undefined,
        search_location: debouncedTextFilters.search_location || undefined,
        notes: debouncedTextFilters.notes || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })
      .then((response) => {
        if (cancelled) return;
        setJobs(response.items);
        setTotal(response.total);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load jobs");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status, minScore, debouncedTextFilters, sortBy, sortDir, page, pageSize]);

  function toggleSort(column: string) {
    if (sortBy === column) {
      setSortDir(sortDir === "ASC" ? "DESC" : "ASC");
    } else {
      setSortBy(column);
      setSortDir("DESC");
    }
    setSelectedPreset(null);
  }

  async function handleStatusChange(jobId: string, newStatus: ApplicationStatus) {
    try {
      const updated = await api.updateJob(jobId, { status: newStatus });
      setJobs((current) => current.map((job) => (job.job_id === jobId ? updated : job)));
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Update failed",
        message: err instanceof ApiError ? err.message : "Could not update job status",
      });
    }
  }

  async function handleFindNextUnreviewed() {
    setFindingNext(true);
    try {
      // The highest-scoring job nobody's looked at yet -- opening it
      // (JobDetailPage) silently marks it "viewed", so clicking this
      // again lands on the next one, forming a review loop without
      // tracking an index anywhere.
      const response = await api.listJobs({
        status: "not_applied",
        sort_by: "match_score",
        sort_dir: "DESC",
        limit: 1,
      });
      if (response.items.length === 0) {
        notifications.show({
          color: "blue",
          title: "All caught up",
          message: "No unreviewed jobs left.",
        });
        return;
      }
      navigate(`/jobs/${response.items[0].job_id}`);
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Could not find the next job",
        message: err instanceof ApiError ? err.message : "Please try again",
      });
    } finally {
      setFindingNext(false);
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
      const response = await api.listJobs({
        status: status ?? undefined,
        min_score: minScore === "" ? undefined : minScore,
        title: debouncedTextFilters.title || undefined,
        company: debouncedTextFilters.company || undefined,
        location: debouncedTextFilters.location || undefined,
        posted: debouncedTextFilters.posted || undefined,
        salary: debouncedTextFilters.salary || undefined,
        employment_type: debouncedTextFilters.employment_type || undefined,
        seniority: debouncedTextFilters.seniority || undefined,
        applicants: debouncedTextFilters.applicants || undefined,
        job_id: debouncedTextFilters.job_id || undefined,
        search_location: debouncedTextFilters.search_location || undefined,
        notes: debouncedTextFilters.notes || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setJobs(response.items);
      setTotal(response.total);
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

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function cellStyle(width: number): CSSProperties {
    return {
      width,
      height: 40,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
      verticalAlign: "middle",
    };
  }

  function renderFilterControl(def: ColumnDef) {
    if (def.filter === "text") {
      return (
        <TextInput
          size="xs"
          aria-label={`Filter by ${def.label}`}
          placeholder="Filter..."
          title="Prefix with - to exclude, e.g. -senior"
          value={textFilters[def.key as keyof TextFilters]}
          onChange={(event) =>
            setTextFilter(def.key as keyof TextFilters, event.currentTarget.value)
          }
        />
      );
    }
    if (def.filter === "score") {
      return (
        <NumberInput
          size="xs"
          aria-label="Minimum score"
          placeholder="Min"
          min={0}
          max={100}
          value={minScore}
          onChange={(value) => {
            setMinScore(value === "" ? "" : Number(value));
            setSelectedPreset(null);
          }}
        />
      );
    }
    if (def.filter === "status") {
      return (
        <Select
          size="xs"
          aria-label="Filter by status"
          placeholder="All"
          clearable
          data={APPLICATION_STATUSES}
          value={status}
          onChange={(value) => {
            setStatus(value as ApplicationStatus | null);
            setSelectedPreset(null);
          }}
        />
      );
    }
    return null;
  }

  function renderCell(job: Job, key: ColumnKey) {
    switch (key) {
      case "scraped_at":
        return job.scraped_at.slice(0, 10);
      case "title":
        return (
          <Group gap={6} wrap="nowrap">
            <Anchor component={Link} to={`/jobs/${job.job_id}`}>
              {job.title || "(untitled)"}
            </Anchor>
            <ActionIcon
              component="a"
              href={job.job_url}
              target="_blank"
              rel="noreferrer"
              variant="subtle"
              color="gray"
              size="sm"
              title="Open on LinkedIn"
            >
              <IconExternalLink size={14} />
            </ActionIcon>
          </Group>
        );
      case "company":
        return job.company;
      case "location":
        return job.location_entity || job.location;
      case "posted":
        return isStalePosted(job.posted) ? (
          <Text size="sm" c="orange" title="Posted a while ago -- may no longer be open">
            {job.posted}
          </Text>
        ) : (
          job.posted
        );
      case "salary":
        return job.salary;
      case "employment_type":
        return job.employment_type;
      case "seniority":
        return job.seniority;
      case "applicants":
        return job.applicants;
      case "match_score":
        return job.match_score !== null ? (
          <Badge color={job.match_score >= 50 ? "green" : "gray"}>
            {job.match_score.toFixed(0)}
          </Badge>
        ) : (
          <Text c="dimmed" size="sm">
            --
          </Text>
        );
      case "job_id":
        return (
          <Text size="sm" c="dimmed">
            {job.job_id}
          </Text>
        );
      case "search_location":
        return job.search_location;
      case "notes":
        return job.notes ? (
          <Tooltip label={job.notes} multiline maw={320}>
            <Text size="sm" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
              {job.notes}
            </Text>
          </Tooltip>
        ) : (
          <Text size="sm" c="dimmed">
            --
          </Text>
        );
      case "status":
        return (
          <Select
            size="xs"
            data={APPLICATION_STATUSES}
            value={job.application_status}
            onChange={(value) =>
              value && handleStatusChange(job.job_id, value as ApplicationStatus)
            }
          />
        );
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          Filter and sort using the row under the column headers. Drag a header to reorder
          columns, drag its right edge to resize.
        </Text>
        <Group gap="sm">
          <Button
            onClick={handleFindNextUnreviewed}
            loading={findingNext}
            variant="light"
            leftSection={<IconPlayerTrackNext size={16} />}
          >
            Next unreviewed job
          </Button>
          <Button onClick={handleRecalculate} loading={recalculating} variant="light">
            Recalculate scores
          </Button>
        </Group>
      </Group>

      <Group gap="sm" wrap="wrap">
        <Select
          size="sm"
          placeholder="Load preset..."
          aria-label="Load filter preset"
          data={presets.map((p) => p.name)}
          value={selectedPreset}
          onChange={applyPreset}
          // Mantine's Select defaults allowDeselect to true, which clears
          // the value (calls onChange(null)) when you click the option
          // that's already selected -- exactly the case of reapplying
          // the currently-loaded preset after tweaking a filter by hand.
          allowDeselect={false}
          w={200}
        />
        {selectedPreset && (
          <ActionIcon
            color="red"
            variant="subtle"
            onClick={handleDeletePreset}
            title="Delete this preset"
          >
            <IconTrash size={16} />
          </ActionIcon>
        )}
        <TextInput
          size="sm"
          placeholder="New preset name"
          aria-label="New preset name"
          value={newPresetName}
          onChange={(event) => setNewPresetName(event.currentTarget.value)}
          w={200}
        />
        <Button size="sm" variant="light" onClick={handleSavePreset} disabled={!newPresetName.trim()}>
          Save current filters as preset
        </Button>
      </Group>

      {error && (
        <Alert color="red" title="Error">
          {error}
        </Alert>
      )}

      <Paper withBorder>
        <div style={{ overflow: "auto", maxHeight: TABLE_MAX_HEIGHT }}>
          <Table
            striped
            highlightOnHover
            style={{
              tableLayout: "fixed",
              minWidth: columnOrder.reduce((sum, key) => sum + widths[key], 0),
            }}
          >
            <Table.Thead>
              <Table.Tr>
                {columnOrder.map((key) => {
                  const def = COLUMN_DEFS[key];
                  return (
                    <ResizableTh
                      key={key}
                      width={widths[key]}
                      top={0}
                      onResizeStart={(startX) => startResize(key, startX)}
                      onClick={def.sortKey ? () => toggleSort(def.sortKey!) : undefined}
                      draggable
                      isDragging={draggedKey === key}
                      onDragStart={() => setDraggedKey(key)}
                      onDragOver={(event: DragEvent) => event.preventDefault()}
                      onDrop={() => handleDrop(key)}
                    >
                      {def.label}
                      {def.sortKey === sortBy && (sortDir === "ASC" ? " ^" : " v")}
                    </ResizableTh>
                  );
                })}
              </Table.Tr>
              <Table.Tr>
                {columnOrder.map((key) => {
                  const def = COLUMN_DEFS[key];
                  return (
                    <Table.Th
                      key={key}
                      style={{
                        width: widths[key],
                        position: "sticky",
                        top: HEADER_ROW_HEIGHT,
                        zIndex: 2,
                        backgroundColor: "var(--mantine-color-body)",
                        padding: 4,
                      }}
                    >
                      {renderFilterControl(def)}
                    </Table.Th>
                  );
                })}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {jobs.map((job) => (
                <Table.Tr key={job.job_id}>
                  {columnOrder.map((key) => (
                    <Table.Td key={key} style={cellStyle(widths[key])}>
                      {renderCell(job, key)}
                    </Table.Td>
                  ))}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </div>

        {loading && (
          <Group justify="center" p="md">
            <Loader size="sm" />
          </Group>
        )}

        {!loading && jobs.length === 0 && !error && (
          <Text c="dimmed" ta="center" p="md">
            No jobs match the current filters.
          </Text>
        )}
      </Paper>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center" }}>
        <Group gap="md">
          <Text c="dimmed" size="sm">
            {total} job(s) total
          </Text>
        </Group>
        <Group gap="sm">
          <MantinePagination value={page} onChange={setPage} total={totalPages} />
          <Text size="sm" c="dimmed">
            Per page
          </Text>
          <Select
            size="sm"
            aria-label="Per page"
            data={PAGE_SIZE_OPTIONS}
            value={String(pageSize)}
            onChange={(value) => value && setPageSize(Number(value))}
            w={80}
          />
        </Group>
        <div />
      </div>
    </Stack>
  );
}
