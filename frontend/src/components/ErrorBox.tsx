import type { ShownError } from "@/lib/errors";

export function ErrorBox({ error }: { error: ShownError }) {
  return (
    <div role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
      <p>{error.message}</p>
      {error.details.length > 0 && (
        <ul className="mt-2 list-disc pl-5">
          {error.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
