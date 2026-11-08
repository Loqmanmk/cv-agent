import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplicationForm } from "@/components/ApplicationForm";

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const offerBody = {
  text: "Développeur Full Stack\nReact.js, Node.js, SQL Server",
  truncated: false,
  source_url: "https://example.com/final",
};

function setup(disabled = false) {
  const onSubmit = vi.fn();
  const user = userEvent.setup({ applyAccept: false });
  render(<ApplicationForm onSubmit={onSubmit} disabled={disabled} />);
  return { onSubmit, user };
}

async function fetchOffer(
  user: ReturnType<typeof userEvent.setup>,
  url = "https://example.com/job",
) {
  await user.type(screen.getByLabelText(/link to the job offer/i), url);
  await user.click(screen.getByRole("button", { name: "Fetch the offer" }));
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Job link field", () => {
  it("fills the job offer box with the fetched text and says where it came from", async () => {
    fetchMock.mockResolvedValue(jsonResponse(offerBody));
    const { user } = setup();

    await fetchOffer(user);

    expect(await screen.findByLabelText("Job offer")).toHaveValue(offerBody.text);
    expect(
      await screen.findByText(/Offer fetched from https:\/\/example.com\/final/),
    ).toBeInTheDocument();
  });

  it("sends the link to the server", async () => {
    fetchMock.mockResolvedValue(jsonResponse(offerBody));
    const { user } = setup();

    await fetchOffer(user);
    await screen.findByText(/Offer fetched/);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/job-offers/fetch");
    expect(JSON.parse(init.body as string)).toEqual({ url: "https://example.com/job" });
  });

  it("lets the user edit the fetched text and then submit it", async () => {
    fetchMock.mockResolvedValue(jsonResponse(offerBody));
    const { onSubmit, user } = setup();
    await fetchOffer(user);
    await screen.findByText(/Offer fetched/);

    await user.type(screen.getByLabelText("Job offer"), "\nCompany: Duroc");
    await user.upload(screen.getByLabelText(/cv file/i), new File(["content"], "cv.docx"));
    await user.click(screen.getByRole("button", { name: "Create my application" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ jobText: `${offerBody.text}\nCompany: Duroc` }),
    );
  });

  it("warns when the text was cut", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ...offerBody, truncated: true }));
    const { user } = setup();

    await fetchOffer(user);

    expect(await screen.findByText(/the end was cut/)).toBeInTheDocument();
  });

  it("shows the message of the server when the page cannot be fetched", async () => {
    const detail = "This link cannot be fetched. Use the public address of the page.";
    fetchMock.mockResolvedValue(jsonResponse({ detail }, 422));
    const { user } = setup();

    await fetchOffer(user, "http://localhost/");

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
    expect(screen.getByLabelText("Job offer")).toHaveValue("");
  });

  it("explains that the server cannot be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { user } = setup();

    await fetchOffer(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("asks for a link when the field is empty and calls nothing", async () => {
    const { user } = setup();

    await user.click(screen.getByRole("button", { name: "Fetch the offer" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Paste the link of the job offer.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("locks the link field and the button while fetching", async () => {
    fetchMock.mockReturnValue(new Promise(() => {}));
    const { user } = setup();

    await fetchOffer(user);

    expect(await screen.findByRole("button", { name: "Fetching…" })).toBeDisabled();
    expect(screen.getByLabelText(/link to the job offer/i)).toBeDisabled();
  });

  it("keeps the whole form locked while an application is being created", () => {
    setup(true);

    expect(screen.getByLabelText(/link to the job offer/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Fetch the offer" })).toBeDisabled();
  });

  it("clears the job offer error once text has been fetched", async () => {
    fetchMock.mockResolvedValue(jsonResponse(offerBody));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Create my application" }));
    expect(screen.getByText("Paste the job offer.")).toBeInTheDocument();

    await fetchOffer(user);

    await screen.findByText(/Offer fetched/);
    expect(screen.queryByText("Paste the job offer.")).not.toBeInTheDocument();
  });
});
