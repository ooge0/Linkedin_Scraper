import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconArrowLeft, IconExternalLink } from "@tabler/icons-react";

import { api, ApiError } from "../api/client";
import { APPLICATION_STATUSES, type ApplicationStatus, type Job, type MatchDetail } from "../api/types";

// If a job has sat in "applied" this many days with no status change,
// the detail page suggests following up -- deliberately coarse (like
// JobsPage's "stale posting" highlight) rather than a configurable
// setting, since the point is just a nudge, not a precise SLA.
const FOLLOW_UP_REMINDER_DAYS = 14;

function daysSince(isoTimestamp: string): number {
  const elapsedMs = Date.now() - new Date(isoTimestamp).getTime();
  return Math.floor(elapsedMs / (1000 * 60 * 60 * 24));
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [interviewDate, setInterviewDate] = useState("");
  const [savingTracking, setSavingTracking] = useState(false);
  const [breakdown, setBreakdown] = useState<MatchDetail[]>([]);

  useEffect(() => {
    if (!jobId) return;
    setLoading(true);
    setError(null);

    api
      .getJob(jobId)
      .then((data) => {
        setJob(data);
        setNotes(data.notes);
        setInterviewDate(data.interview_date);

        // Opening a job's detail page is itself a signal it's been looked
        // at -- silently promote it from "not applied" to "viewed" so the
        // "Next unreviewed job" button (JobsPage) doesn't keep landing on
        // the same one. Best-effort: on failure the page still works, the
        // job just stays "not applied".
        if (data.application_status === "not_applied") {
          api.updateJob(jobId, { status: "viewed" }).then(setJob).catch(() => {});
        }
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError && err.status === 404
            ? "Job not found"
            : "Failed to load job",
        );
      })
      .finally(() => setLoading(false));

    // Best-effort: if this fails, the page still works, it just won't
    // show the "why this score" breakdown.
    api
      .getScoreBreakdown(jobId)
      .then(setBreakdown)
      .catch(() => setBreakdown([]));
  }, [jobId]);

  async function handleStatusChange(newStatus: ApplicationStatus) {
    if (!jobId) return;
    try {
      const updated = await api.updateJob(jobId, { status: newStatus });
      setJob(updated);
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Update failed",
        message: err instanceof ApiError ? err.message : "Could not update status",
      });
    }
  }

  async function handleSaveTracking() {
    if (!jobId) return;
    setSavingTracking(true);
    try {
      const updated = await api.updateJob(jobId, { notes, interview_date: interviewDate });
      setJob(updated);
      notifications.show({ color: "green", title: "Saved", message: "Notes updated" });
    } catch (err) {
      notifications.show({
        color: "red",
        title: "Save failed",
        message: err instanceof ApiError ? err.message : "Could not save notes",
      });
    } finally {
      setSavingTracking(false);
    }
  }

  if (loading) {
    return (
      <Group justify="center" p="xl">
        <Loader />
      </Group>
    );
  }

  if (error || !job) {
    return (
      <Stack gap="md">
        <Anchor component={Link} to="/">
          <Group gap={4}>
            <IconArrowLeft size={16} /> Back to jobs
          </Group>
        </Anchor>
        <Alert color="red" title="Error">
          {error ?? "Job not found"}
        </Alert>
      </Stack>
    );
  }

  return (
    <Stack gap="md" maw={900}>
      <Anchor component={Link} to="/">
        <Group gap={4}>
          <IconArrowLeft size={16} /> Back to jobs
        </Group>
      </Anchor>

      <Paper withBorder p="lg">
        <Stack gap="xs">
          <Group justify="space-between" align="flex-start">
            <div>
              <Title order={2}>{job.title || "(untitled)"}</Title>
              <Text c="dimmed">
                {job.company}
                {(job.location_entity || job.location) && ` · ${job.location_entity || job.location}`}
              </Text>
            </div>
            <Button
              component="a"
              href={job.job_url}
              target="_blank"
              rel="noreferrer"
              variant="light"
              rightSection={<IconExternalLink size={16} />}
            >
              Open on LinkedIn
            </Button>
          </Group>

          <Group gap="lg" mt="xs">
            {job.salary && <Text size="sm">Salary: {job.salary}</Text>}
            {job.employment_type && <Text size="sm">{job.employment_type}</Text>}
            {job.seniority && <Text size="sm">{job.seniority}</Text>}
            {job.workplace_type && <Text size="sm">{job.workplace_type}</Text>}
            {job.applicants && <Text size="sm">{job.applicants}</Text>}
            {job.posted && <Text size="sm">{job.posted}</Text>}
          </Group>

          {job.skills.length > 0 && (
            <Group gap={6} mt="xs">
              {job.skills.map((skill) => (
                <Badge key={skill} variant="light">
                  {skill}
                </Badge>
              ))}
            </Group>
          )}

          {job.match_score !== null && (
            <Badge color={job.match_score >= 50 ? "green" : "gray"} w="fit-content" mt="xs">
              Match score: {job.match_score.toFixed(0)}
            </Badge>
          )}

          {breakdown.length > 0 && (
            <Stack gap={4} mt="xs">
              <Text size="sm" c="dimmed">
                Why this score:
              </Text>
              <Group gap={6}>
                {breakdown.map((detail) => {
                  const contribution = detail.matched ? detail.weight : 0;
                  return (
                    <Badge
                      key={detail.term}
                      variant={detail.matched ? "filled" : "outline"}
                      color={!detail.matched ? "gray" : contribution >= 0 ? "green" : "red"}
                    >
                      {contribution > 0 ? "+" : ""}
                      {contribution} {detail.term}
                      {detail.matched_in_title ? " (title)" : ""}
                    </Badge>
                  );
                })}
              </Group>
            </Stack>
          )}
        </Stack>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={4} mb="sm">
          Description
        </Title>
        <Text style={{ whiteSpace: "pre-wrap" }}>{job.description || "No description saved."}</Text>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={4} mb="sm">
          Application tracking
        </Title>
        <Stack gap="sm">
          {job.application_status === "applied" &&
            job.status_updated_at &&
            daysSince(job.status_updated_at) >= FOLLOW_UP_REMINDER_DAYS && (
              <Alert color="yellow" title="Consider following up">
                Applied {daysSince(job.status_updated_at)} days ago with no status change since.
              </Alert>
            )}
          <Group grow align="flex-start">
            <Select
              label="Status"
              data={APPLICATION_STATUSES}
              value={job.application_status}
              onChange={(value) => value && handleStatusChange(value as ApplicationStatus)}
            />
            <TextInput
              type="date"
              label="Interview date"
              value={interviewDate}
              onChange={(event) => setInterviewDate(event.currentTarget.value)}
            />
          </Group>
          <Textarea
            label="Notes"
            value={notes}
            onChange={(event) => setNotes(event.currentTarget.value)}
            autosize
            minRows={3}
          />
          <Group justify="flex-end">
            <Button
              onClick={handleSaveTracking}
              loading={savingTracking}
              disabled={notes === job.notes && interviewDate === job.interview_date}
            >
              Save
            </Button>
          </Group>
        </Stack>
      </Paper>
    </Stack>
  );
}
