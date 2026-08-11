import type {
  Application,
  ApplicationResource,
  Decision,
  Message,
} from "@/types/decisionflow";

export type CrossSearchResultKind =
  | "application"
  | "message"
  | "decision"
  | "resource";

export type CrossSearchResult = {
  id: string;
  kind: CrossSearchResultKind;
  applicationId?: string;
  applicationTitle: string;
  title: string;
  excerpt: string;
  score: number;
};

type CrossSearchInput = {
  applications: Application[];
  messages: Message[];
  decisions: Decision[];
  resources: ApplicationResource[];
  query: string;
};

function normalize(value: unknown): string {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("ja")
    .replace(/\s+/g, " ")
    .trim();
}

function excerpt(value: string): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length > 160 ? `${compact.slice(0, 157)}...` : compact;
}

export function searchDecisionFlow({
  applications,
  messages,
  decisions,
  resources,
  query,
}: CrossSearchInput): CrossSearchResult[] {
  const terms = normalize(query).split(" ").filter(Boolean);
  if (terms.length === 0) return [];

  const applicationTitleById = new Map(
    applications.map((item) => [item.ds_applicationid, item.ds_name]),
  );
  const results: CrossSearchResult[] = [];

  const add = ({
    id,
    kind,
    applicationId,
    title,
    content,
  }: Omit<CrossSearchResult, "applicationTitle" | "excerpt" | "score"> & {
    content: string;
  }) => {
    const normalizedTitle = normalize(title);
    const normalizedContent = normalize(content);
    const haystack = `${normalizedTitle} ${normalizedContent}`;
    if (!terms.every((term) => haystack.includes(term))) return;

    const titleMatches = terms.filter((term) =>
      normalizedTitle.includes(term),
    ).length;
    results.push({
      id,
      kind,
      applicationId,
      applicationTitle: applicationId
        ? (applicationTitleById.get(applicationId) ?? "関連申請")
        : title,
      title,
      excerpt: excerpt(content || title),
      score: titleMatches * 10 + terms.length,
    });
  };

  applications.forEach((item) =>
    add({
      id: `application:${item.ds_applicationid}`,
      kind: "application",
      applicationId: item.ds_applicationid,
      title: item.ds_name,
      content: [
        item.ds_body,
        item.ds_aiapplicationsummary,
        item.ds_aiconversationsummary,
        item.ds_aidecisionoptiontext,
        item.ds_aidecisioncomment,
      ]
        .filter(Boolean)
        .join(" "),
    }),
  );
  messages.forEach((item) =>
    add({
      id: `message:${item.ds_messageid}`,
      kind: "message",
      applicationId: item._ds_applicationid_value,
      title: item.ds_name,
      content: item.ds_body ?? "",
    }),
  );
  decisions.forEach((item) =>
    add({
      id: `decision:${item.ds_decisionid}`,
      kind: "decision",
      applicationId: item._ds_applicationid_value,
      title: item.ds_name,
      content: item.ds_rationale ?? "",
    }),
  );
  resources.forEach((item) =>
    add({
      id: `resource:${item.ds_applicationresourceid}`,
      kind: "resource",
      applicationId: item._ds_applicationid_value,
      title: item.ds_name,
      content: [item.ds_description, item.ds_url].filter(Boolean).join(" "),
    }),
  );

  return results.sort(
    (left, right) =>
      right.score - left.score ||
      left.applicationTitle.localeCompare(right.applicationTitle, "ja") ||
      left.title.localeCompare(right.title, "ja"),
  );
}
