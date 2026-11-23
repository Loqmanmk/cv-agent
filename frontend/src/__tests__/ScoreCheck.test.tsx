import { render, screen, within } from "@testing-library/react";
import userEvent, { type UserEvent } from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationForm } from "@/components/ApplicationForm";
import { ApplicationPanel } from "@/components/ApplicationPanel";
import { scoreApplication } from "@/lib/api";

import { jsonResponse } from "./helpers/http";

const fetchMock = vi.fn();
const cv = new File(["content"], "cv.docx");

function scoreBody(value: number | null = 71) {
  return {
    job_title: "Stagiaire DataLab",
    company: "Coface",
    report: {
      matched_skills: ["Python", "SQL"],
      missing_skills: [
        { name: "Kubernetes", required: true, group: "DevOps" },
        { name: "Terraform", required: false, group: null },
      ],
      changes: [],
      score: {
        value,
        required_matched: 2,
        required_total: 3,
        nice_matched: 1,
        nice_total: 1,
      },
    },
  };
}

async function fill(user: UserEvent) {
  await user.upload(screen.getByLabelText(/cv file/i), cv);
  await user.type(screen.getByLabelText("Job offer"), "Acme seeks an intern.");
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("checking the match score before creating", () => {
  it("sends the CV and the offer to the score endpoint", async () => {
    fetchMock.mockResolvedValue(jsonResponse(scoreBody()));

    const preview = await scoreApplication({ cvFile: cv, jobText: "Acme seeks an intern." });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/applications/score");
    expect((init.body as FormData).get("job_text")).toBe("Acme seeks an intern.");
    expect((init.body as FormData).get("cv_file")).toBeInstanceOf(File);
    expect(preview.report.score.value).toBe(71);
    expect(preview.company).toBe("Coface");
  });

  it("refuses an answer that is not a score", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ nope: true }));

    await expect(scoreApplication({ cvFile: null, jobText: "x" })).rejects.toThrow(
      "unexpected answer",
    );
  });

  it("checks the form first, like creating does", async () => {
    const onCheckScore = vi.fn();
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationForm onSubmit={vi.fn()} onCheckScore={onCheckScore} />);

    await user.click(screen.getByRole("button", { name: "Check my match score" }));
    expect(onCheckScore).not.toHaveBeenCalled();
    expect(screen.getByText("Paste the job offer.")).toBeInTheDocument();

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Check my match score" }));
    expect(onCheckScore).toHaveBeenCalledWith(
      expect.objectContaining({ cvFile: cv, jobText: "Acme seeks an intern." }),
    );
  });

  it("shows the score, the verdict and the skills, without creating anything", async () => {
    fetchMock.mockResolvedValue(jsonResponse(scoreBody()));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Check my match score" }));

    const card = await screen.findByRole("region", { name: "Match score" });
    expect(within(card).getByText(/Stagiaire DataLab — Coface/)).toBeInTheDocument();
    expect(within(card).getByRole("meter")).toHaveAttribute("aria-valuenow", "71");
    expect(within(card).getByText(/Good match/)).toBeInTheDocument();
    expect(within(card).getByText(/Python, SQL/)).toBeInTheDocument();
    expect(within(card).getByText(/Kubernetes/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("says so when the offer names no skills to compare", async () => {
    fetchMock.mockResolvedValue(jsonResponse(scoreBody(null)));
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Check my match score" }));

    expect(await screen.findByText(/no score to give/)).toBeInTheDocument();
  });

  it("shows why the score could not be computed", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ detail: "The AI service is busy or out of quota." }, 503),
    );
    const user = userEvent.setup({ applyAccept: false });
    render(<ApplicationPanel />);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Check my match score" }));

    expect(await screen.findByText("The AI service is busy or out of quota.")).toBeInTheDocument();
  });
});
