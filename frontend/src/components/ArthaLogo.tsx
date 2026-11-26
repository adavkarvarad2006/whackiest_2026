import React from "react";

interface ArthaLogoProps {
  variant?: "dark" | "light";
  showText?: boolean;
  className?: string;
}

export function ArthaLogo({
  variant = "light",
  showText = true,
  className = "",
}: ArthaLogoProps) {
  const stroke = variant === "dark" ? "#FFFFFF" : "#090909";
  const textColor = variant === "dark" ? "text-white" : "text-[#090909]";

  return (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <svg
        width="28"
        height="28"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="ArthaLens Logo"
      >
        <rect
          x="1.5"
          y="1.5"
          width="29"
          height="29"
          rx="8"
          stroke={stroke}
          strokeWidth="1.75"
        />
        {/* Abstract geometric letter A */}
        <path
          d="M16 7.5L8.5 24.5H12.2L16 15.6L19.8 24.5H23.5L16 7.5Z"
          fill={stroke}
        />
        <circle cx="16" cy="21" r="2" fill={stroke} />
      </svg>
      {showText && (
        <span className={`text-[17px] font-semibold tracking-tight ${textColor}`}>
          ArthaLens
        </span>
      )}
    </div>
  );
}
