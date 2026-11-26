"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

interface AssistantMarkdownProps {
  content: string;
}

function isSafeHref(href?: string): boolean {
  if (!href) return false;
  const trimmed = href.trim().toLowerCase();
  return (
    trimmed.startsWith("https://") ||
    trimmed.startsWith("http://") ||
    trimmed.startsWith("mailto:") ||
    trimmed.startsWith("/") ||
    trimmed.startsWith("#")
  );
}

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-4 first:mt-0 mb-2 text-base font-bold tracking-tight text-[#111111] dark:text-[#F5F5F5]">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-4 first:mt-0 mb-2 text-[15px] font-semibold tracking-tight text-[#111111] dark:text-[#F5F5F5]">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3.5 first:mt-0 mb-1.5 text-sm font-semibold text-[#111111] dark:text-[#F5F5F5]">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-3 first:mt-0 mb-1 text-[13px] font-semibold text-[#111111] dark:text-[#F5F5F5]">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="my-2 first:mt-0 last:mb-0 text-sm leading-relaxed text-[#171717] dark:text-[#F5F5F5]">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[#111111] dark:text-white">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-[#171717] dark:text-[#E5E5E5]">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="my-2.5 first:mt-0 last:mb-0 list-disc pl-5 space-y-1.5 text-sm leading-relaxed text-[#171717] dark:text-[#F5F5F5] marker:text-[#666666] dark:marker:text-[#A3A3A3]">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2.5 first:mt-0 last:mb-0 list-decimal pl-5 space-y-1.5 text-sm leading-relaxed text-[#171717] dark:text-[#F5F5F5] marker:font-medium marker:text-[#666666] dark:marker:text-[#A3A3A3]">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="pl-0.5 text-[#171717] dark:text-[#F5F5F5] [&>p]:my-1">{children}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-[#111111] dark:border-[#A3A3A3] pl-3.5 py-1 text-[13px] text-[#666666] dark:text-[#A3A3A3] bg-white/80 dark:bg-[#2A2A2A] rounded-r-xl">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-[#E5E5E5] dark:border-[#333333]" />,
  a: ({ href, children }) => {
    if (!isSafeHref(href)) {
      return <span className="underline decoration-[#666666] dark:decoration-[#A3A3A3]">{children}</span>;
    }
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-[#2563EB] dark:text-[#60A5FA] underline underline-offset-2 decoration-[#2563EB]/60 dark:decoration-[#60A5FA]/60 hover:opacity-80"
      >
        {children}
      </a>
    );
  },
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-2xl border border-[#E5E5E5] dark:border-[#333333] bg-white dark:bg-[#141414]">
      <table className="w-full min-w-[360px] border-collapse text-left text-xs tabular-nums text-[#171717] dark:text-[#F5F5F5]">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[#EFEFEF] dark:bg-[#262626] border-b border-[#E5E5E5] dark:border-[#333333] text-[#111111] dark:text-[#F5F5F5]">
      {children}
    </thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-[#E5E5E5] dark:divide-[#2E2E2E] text-[#171717] dark:text-[#F5F5F5]">
      {children}
    </tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-[#FAFAFA] dark:hover:bg-[#262626]/60 transition-colors">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3.5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-[#111111] dark:text-[#F5F5F5] whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3.5 py-2.5 text-xs leading-snug align-top text-[#171717] dark:text-[#F5F5F5]">
      {children}
    </td>
  ),
  pre: ({ children }) => (
    <div className="my-3 overflow-hidden rounded-2xl border border-[#262626] dark:border-[#404040] bg-[#111111]">
      <pre className="overflow-x-auto p-3.5 text-xs leading-relaxed font-mono text-[#F5F5F5] [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-xs [&_code]:font-mono [&_code]:text-inherit">
        {children}
      </pre>
    </div>
  ),
  code: ({ className, children, ...props }) => {
    const isCodeBlock = Boolean(
      className?.includes("language-") ||
        className?.includes("hljs") ||
        String(children).includes("\n")
    );
    if (isCodeBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded-md border border-[#E5E5E5] dark:border-[#404040] bg-[#EDEDED] dark:bg-[#2A2A2A] px-1.5 py-0.5 text-[12px] font-mono text-[#111111] dark:text-[#F5F5F5]"
        {...props}
      >
        {children}
      </code>
    );
  },
};

export function AssistantMarkdown({ content }: AssistantMarkdownProps) {
  return (
    <div className="arthalens-md space-y-1 break-words text-[#171717] dark:text-[#F5F5F5]">
      <ReactMarkdown
        remarkPlugins={[[remarkGfm, { singleTilde: false }]]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
