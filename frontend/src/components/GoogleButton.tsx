import { googleStartUrl } from "@/lib/googleSignIn";

export function GoogleButton() {
  return (
    <div>
      <a
        href={googleStartUrl()}
        className="block w-full rounded border border-gray-300 bg-white px-4 py-2 text-center text-sm font-medium hover:bg-gray-50"
      >
        Continue with Google
      </a>
      <div className="mt-4 flex items-center gap-3 text-xs text-gray-500" aria-hidden="true">
        <span className="h-px flex-1 bg-gray-200" />
        or with your email
        <span className="h-px flex-1 bg-gray-200" />
      </div>
    </div>
  );
}
