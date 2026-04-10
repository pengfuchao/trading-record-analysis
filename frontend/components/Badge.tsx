interface BadgeProps {
  label: string;
  variant?: "win" | "loss" | "breakeven" | "neutral";
}

const variantMap: Record<string, string> = {
  win: "bg-green-900 text-green-300",
  loss: "bg-red-900 text-red-300",
  breakeven: "bg-gray-700 text-gray-300",
  neutral: "bg-blue-900 text-blue-300",
};

export default function Badge({ label, variant = "neutral" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${variantMap[variant]}`}>
      {label}
    </span>
  );
}
