type Props = {
  password: string;
  confirm: string;
  onPassword: (value: string) => void;
  onConfirm: (value: string) => void;
  disabled?: boolean;
  label?: string;
};

const FIELD = "mt-1 block w-full rounded border border-gray-300 p-2 text-sm";

export function PasswordFields({
  password,
  confirm,
  onPassword,
  onConfirm,
  disabled = false,
  label = "Password",
}: Props) {
  return (
    <>
      <div>
        <label htmlFor="new-password" className="block text-sm font-medium">
          {label}
        </label>
        <input
          id="new-password"
          type="password"
          autoComplete="new-password"
          aria-describedby="new-password-help"
          value={password}
          disabled={disabled}
          onChange={(event) => onPassword(event.target.value)}
          className={FIELD}
        />
        <p id="new-password-help" className="mt-1 text-xs text-gray-500">
          At least 12 characters. A few random words are easy to remember and hard to guess.
        </p>
      </div>
      <div>
        <label htmlFor="confirm-password" className="block text-sm font-medium">
          Repeat the password
        </label>
        <input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          disabled={disabled}
          onChange={(event) => onConfirm(event.target.value)}
          className={FIELD}
        />
      </div>
    </>
  );
}
