import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
