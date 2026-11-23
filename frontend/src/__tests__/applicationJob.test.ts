import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  createApplication,
  MAX_WAIT_MS,
  POLL_INTERVAL_MS,
  type ApplicationRequestValues,
  type GenerationStage,
} from "@/lib/api";

import { makeDoneJob, makeFailedJob, makeRunningJob } from "./fixtures";
import { jsonResponse } from "./helpers/http";

const fetchMock = vi.fn();

const values: ApplicationRequestValues = {
  cvFile: null,
  jobText: "Acme seeks an intern.",
  includePhoto: true,
  includeLetter: true,
};

/** Runs the generation while the fake clock moves on, and returns how it ended. */
async function settle(promise: Promise<unknown>): Promise<{ value?: unknown; error?: unknown }> {
  const outcome = promise.then(
    (value) => ({ value }),
    (error: unknown) => ({ error }),
  );
  await vi.runAllTimersAsync();
  return outcome;
}

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("following a generation in the background", () => {
  it("asks for news until the job is done and reports each stage", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeRunningJob("queued"), 202))
      .mockResolvedValueOnce(jsonResponse(makeRunningJob("reading")))
      .mockResolvedValueOnce(jsonResponse(makeRunningJob("tailoring")))
      .mockResolvedValueOnce(jsonResponse(makeDoneJob()));
    const stages: GenerationStage[] = [];

    const { value } = await settle(
      createApplication(values, undefined, (stage) => stages.push(stage)),
    );

    expect(value).toMatchObject({ company: "Coface" });
    expect(stages).toEqual(["queued", "reading", "tailoring", "finished"]);
    const checked = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(checked[0]).toBe("http://api.test/applications/jobs/job-1");
    expect(checked[1].method).toBe("GET");
  });

  it("waits between two checks instead of asking all the time", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeRunningJob(), 202))
      .mockResolvedValueOnce(jsonResponse(makeDoneJob()));
    const promise = createApplication(values);

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS - 1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await promise;

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives the failure of the job with its message and its problems", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeRunningJob(), 202))
      .mockResolvedValueOnce(
        jsonResponse(makeFailedJob(502, "The AI could not produce a faithful result.", ["x"])),
      );

    const { error } = await settle(createApplication(values));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 502,
      message: "The AI could not produce a faithful result.",
      violations: ["x"],
    });
  });

  it("keeps an unexpected failure of the job generic", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(makeFailedJob(500, "internal"), 202));

    const { error } = await settle(createApplication(values));

    expect((error as ApiError).message).toContain("code 500");
  });

  it("goes on after a short network blip: the server keeps working", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeRunningJob(), 202))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(makeDoneJob()));

    const { value } = await settle(createApplication(values));

    expect(value).toMatchObject({ company: "Coface" });
  });

  it("stops when the server stays unreachable", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeRunningJob(), 202))
      .mockRejectedValue(new TypeError("Failed to fetch"));

    const { error } = await settle(createApplication(values));

    expect((error as ApiError).message).toContain("Cannot reach the server");
  });

  it("stops at once when the job has expired", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(makeRunningJob(), 202))
      .mockResolvedValueOnce(jsonResponse({ detail: "This application has expired." }, 404));

    const { error } = await settle(createApplication(values));

    expect(error).toMatchObject({ status: 404, message: "This application has expired." });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("gives up after a very long wait", async () => {
    let now = 0;
    fetchMock.mockImplementation(() => {
      now += MAX_WAIT_MS / 2;
      return Promise.resolve(jsonResponse(makeRunningJob("tailoring")));
    });

    const { error } = await settle(createApplication(values, undefined, undefined, () => now));

    expect((error as ApiError).message).toContain("much longer than usual");
  });

  it("stops following when the user leaves", async () => {
    fetchMock.mockResolvedValue(jsonResponse(makeRunningJob(), 202));
    const controller = new AbortController();
    const promise = createApplication(values, controller.signal);
    const outcome = promise.catch((error: unknown) => error);

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS / 2);
    controller.abort();

    expect(await outcome).toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refuses an answer that is not a job", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ hello: "world" }, 202));

    const { error } = await settle(createApplication(values));

    expect((error as ApiError).message).toBe("The server sent an unexpected answer.");
  });
});
