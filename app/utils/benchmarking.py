from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import ceil
from random import Random
from statistics import mean

from app.schemas.prompt import PromptInput


@dataclass(frozen=True)
class ExpectedDuplicateCluster:
    family_id: str
    prompt_ids: tuple[str, ...]


@dataclass(frozen=True)
class SemanticBenchmarkQuery:
    query: str
    expected_prompt_ids: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkDataset:
    prompts: list[PromptInput]
    expected_duplicate_clusters: list[ExpectedDuplicateCluster] = field(default_factory=list)
    semantic_queries: list[SemanticBenchmarkQuery] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        return {
            "prompts": [prompt.model_dump() for prompt in self.prompts],
            "expected_duplicate_clusters": [asdict(cluster) for cluster in self.expected_duplicate_clusters],
            "semantic_queries": [asdict(query) for query in self.semantic_queries],
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class FamilySpec:
    category: str
    subcategory: str
    goal: str
    variable: str
    query: str
    layer: str

    @property
    def family_id(self) -> str:
        return f"{self.category}.{self.subcategory}"

    @property
    def display_name(self) -> str:
        return f"{self.category.replace('_', ' ').title()} {self.subcategory.replace('_', ' ').title()}"


LAYER_SEQUENCE: tuple[str, ...] = (
    "engine",
    "engine",
    "team",
    "directive",
    "os",
    "engine",
    "team",
    "engine",
    "directive",
    "org",
)

CATEGORY_TAXONOMY: tuple[tuple[str, tuple[tuple[str, str, str, str], ...]], ...] = (
    (
        "billing",
        (
            ("invoice", "resolve invoice questions and explain charge details", "invoice_id", "explain an invoice charge clearly"),
            ("payment", "collect payment information and explain payment status", "payment_status", "help with a payment status issue"),
            ("refund", "review refund eligibility and explain the refund timeline", "refund_request", "explain a refund request and timeline"),
            ("dispute", "guide the caller through a billing dispute workflow", "dispute_reason", "handle a billing dispute call"),
        ),
    ),
    (
        "support",
        (
            ("account", "help the user recover account access and confirm identity", "account_identifier", "restore account access"),
            ("access", "troubleshoot login access and remove blockers", "access_issue", "troubleshoot a login access issue"),
            ("outage", "acknowledge a service outage and explain next steps", "outage_region", "respond to a reported service outage"),
            ("escalation", "escalate a complex support issue with a clear handoff", "escalation_reason", "escalate a support issue cleanly"),
        ),
    ),
    (
        "survey",
        (
            ("intake", "ask the opening survey question naturally and capture the answer", "question_text", "ask an intake survey question"),
            ("followup", "ask a follow-up survey question after an incomplete answer", "followup_question", "ask a survey follow-up question"),
            ("options", "present survey response options and confirm the selected choice", "options", "present response options in a survey"),
            ("closing", "wrap up the survey and thank the user for their input", "survey_topic", "close out a survey call"),
        ),
    ),
    (
        "receptionist",
        (
            ("greeting", "greet the caller warmly and introduce the organization", "organization", "greet a caller warmly"),
            ("routing", "route the caller to the right destination based on need", "destination_team", "route a caller to the right team"),
            ("callback", "offer a callback and confirm the preferred callback details", "callback_time", "offer and confirm a callback"),
            ("voicemail", "collect a voicemail summary and promised follow-up", "message_summary", "take a concise voicemail message"),
        ),
    ),
    (
        "verification",
        (
            ("identity", "verify caller identity using date of birth and confirmation", "date_of_birth", "verify caller identity with date of birth"),
            ("contact", "confirm contact details before proceeding", "phone_number", "confirm caller contact details"),
            ("address", "validate the caller address using flexible phrasing", "mailing_address", "validate a mailing address"),
            ("eligibility", "check verification eligibility before sharing protected details", "eligibility_signal", "check verification eligibility"),
        ),
    ),
    (
        "appointments",
        (
            ("schedule", "schedule an appointment and gather the needed preferences", "appointment_date", "schedule an appointment"),
            ("reschedule", "reschedule an existing appointment smoothly", "reschedule_reason", "reschedule an appointment"),
            ("confirm", "confirm an upcoming appointment and restate the details", "appointment_reference", "confirm an upcoming appointment"),
            ("preparation", "share appointment preparation steps clearly", "prep_requirement", "explain appointment preparation steps"),
        ),
    ),
    (
        "claims",
        (
            ("intake", "collect the first notice of loss and organize claim details", "claim_number", "collect claim intake details"),
            ("status", "provide a clear update on the current claim status", "claim_status", "explain claim status"),
            ("documents", "request supporting claim documents and explain why they matter", "document_type", "request claim documents"),
            ("appeal", "walk through the claim appeal process carefully", "appeal_reason", "explain a claim appeal process"),
        ),
    ),
    (
        "onboarding",
        (
            ("welcome", "welcome a new user and set expectations for onboarding", "first_name", "welcome a new user to onboarding"),
            ("setup", "guide setup steps in order and confirm completion", "setup_step", "guide a setup workflow"),
            ("compliance", "explain onboarding compliance requirements and collect consent", "consent_item", "explain onboarding compliance"),
            ("training", "introduce training steps and confirm understanding", "training_module", "introduce onboarding training"),
        ),
    ),
    (
        "retention",
        (
            ("save", "respond to churn risk with a save conversation", "retention_offer", "handle a customer save conversation"),
            ("objection", "address a retention objection without sounding defensive", "objection_reason", "handle a retention objection"),
            ("offer", "present a retention offer clearly and ethically", "offer_term", "present a retention offer"),
            ("renewal", "discuss renewal timing and confirm next steps", "renewal_date", "discuss a renewal decision"),
        ),
    ),
    (
        "collections",
        (
            ("reminder", "deliver a payment reminder with a respectful tone", "due_date", "deliver a payment reminder"),
            ("promise", "capture a promise-to-pay and confirm the commitment", "promise_date", "capture a promise to pay"),
            ("dispute", "route a collections dispute without escalating tension", "dispute_reason", "handle a collections dispute"),
            ("settlement", "explain settlement options clearly and carefully", "settlement_offer", "explain a settlement option"),
        ),
    ),
    (
        "sales",
        (
            ("qualification", "qualify the prospect and surface the right context", "qualification_goal", "qualify a prospect call"),
            ("demo", "introduce a product demo and confirm success criteria", "demo_goal", "set up a product demo conversation"),
            ("proposal", "explain a proposal and confirm stakeholder concerns", "proposal_term", "walk through a sales proposal"),
            ("closing", "move a late-stage opportunity toward a close", "close_signal", "close a late-stage sales conversation"),
        ),
    ),
    (
        "compliance",
        (
            ("consent", "capture explicit consent before proceeding", "consent_type", "capture explicit consent"),
            ("privacy", "explain privacy boundaries in plain language", "privacy_request", "explain privacy boundaries clearly"),
            ("disclosure", "deliver a required disclosure without sounding robotic", "disclosure_text", "deliver a required disclosure"),
            ("audit", "collect audit evidence and summarize the result", "audit_item", "collect audit evidence"),
        ),
    ),
    (
        "logistics",
        (
            ("tracking", "explain a shipment tracking update clearly", "tracking_number", "explain shipment tracking"),
            ("delivery", "confirm delivery details and resolve blockers", "delivery_window", "confirm delivery details"),
            ("exception", "respond to a shipping exception and explain options", "exception_reason", "handle a shipping exception"),
            ("reschedule", "reschedule a delivery with minimal friction", "reschedule_window", "reschedule a delivery"),
        ),
    ),
    (
        "hr",
        (
            ("recruiting", "guide a recruiting intake conversation", "candidate_role", "run a recruiting intake call"),
            ("interview", "confirm interview logistics and expectations", "interview_slot", "confirm interview logistics"),
            ("offer", "discuss an offer package with clarity and care", "offer_package", "discuss an employment offer"),
            ("employee_onboarding", "prepare a new hire for first-day onboarding", "start_date", "prepare a new hire for onboarding"),
        ),
    ),
    (
        "care",
        (
            ("empathy", "open a care conversation with empathy and reassurance", "care_signal", "sound empathetic in a care conversation"),
            ("checkin", "run a structured care check-in and capture updates", "checkin_topic", "run a structured care check-in"),
            ("medication", "review medication adherence and next actions", "medication_name", "review medication adherence"),
            ("followup", "close the care conversation with a clear follow-up plan", "followup_plan", "close with a care follow-up plan"),
        ),
    ),
    (
        "product",
        (
            ("activation", "guide product activation without losing the user", "activation_code", "guide product activation"),
            ("troubleshooting", "troubleshoot a product issue systematically", "error_code", "troubleshoot a product issue"),
            ("adoption", "encourage adoption by showing the next best step", "feature_name", "encourage product adoption"),
            ("upgrade", "explain upgrade options and confirm fit", "upgrade_plan", "explain product upgrade options"),
        ),
    ),
    (
        "education",
        (
            ("enrollment", "guide a prospective learner through enrollment steps", "program_name", "guide an enrollment conversation"),
            ("advising", "support academic advising with clear recommendations", "advising_goal", "support academic advising"),
            ("attendance", "address attendance concerns and agree on a plan", "attendance_issue", "address attendance concerns"),
            ("assessment", "explain an assessment process and what comes next", "assessment_type", "explain an assessment process"),
        ),
    ),
    (
        "insurance",
        (
            ("policy", "explain policy details in plain language", "policy_number", "explain an insurance policy detail"),
            ("coverage", "clarify coverage and exclusions with confidence", "coverage_question", "clarify insurance coverage"),
            ("premium", "discuss premium changes and billing impact", "premium_change", "discuss an insurance premium change"),
            ("renewal", "guide the renewal review and confirm intent", "renewal_term", "guide an insurance renewal review"),
        ),
    ),
    (
        "utilities",
        (
            ("outage", "respond to a utilities outage with calm next steps", "service_region", "respond to a utilities outage"),
            ("payment", "explain a utilities payment plan and due dates", "payment_plan", "explain a utilities payment plan"),
            ("service", "coordinate a service start or stop request", "service_request", "coordinate a utility service request"),
            ("meter", "handle a meter reading or meter-access conversation", "meter_id", "handle a meter reading conversation"),
        ),
    ),
    (
        "travel",
        (
            ("booking", "guide a travel booking conversation with clear confirmation", "trip_reference", "guide a travel booking"),
            ("rebooking", "rebook disrupted travel and explain trade-offs", "rebooking_reason", "rebook disrupted travel"),
            ("baggage", "address a baggage issue and explain resolution steps", "bag_tag", "handle a baggage issue"),
            ("checkin", "assist with travel check-in and required documents", "checkin_status", "assist with travel check-in"),
        ),
    ),
)

FILLER_TEMPLATES: tuple[str, ...] = (
    "Guide the {category} {subcategory} conversation so the agent can {goal}. Ask for {{{{{variable}}}}} only when it helps move the workflow forward.",
    "Open the {category} {subcategory} workflow by clarifying the user's goal, then capture {{{{{variable}}}}} and confirm the next step.",
    "Support the agent during a {category} {subcategory} request. Keep the exchange precise, explain trade-offs, and validate {{{{{variable}}}}} before continuing.",
    "Handle a {category} {subcategory} scenario by summarizing context, requesting {{{{{variable}}}}}, and guiding the user toward a clear outcome.",
    "Move the {category} {subcategory} task forward with concise language. If details are missing, collect {{{{{variable}}}}} and restate the plan.",
    "For {category} {subcategory}, explain what is happening, gather {{{{{variable}}}}}, and keep the interaction calm and structured.",
    "During a {category} {subcategory} exchange, confirm intent, gather {{{{{variable}}}}}, and surface the most relevant next action.",
    "In the {category} {subcategory} flow, keep the user oriented, capture {{{{{variable}}}}}, and route around confusion without losing momentum.",
    "When running a {category} {subcategory} step, summarize the requirement, collect {{{{{variable}}}}}, and confirm the updated status.",
    "Use a confident but plainspoken tone for {category} {subcategory}. Clarify the issue, request {{{{{variable}}}}}, and close with explicit next steps.",
    "This {category} {subcategory} prompt should reduce friction. Ask for {{{{{variable}}}}}, explain the reason, and continue efficiently.",
    "Help the assistant manage a {category} {subcategory} interaction. Organize the conversation, verify {{{{{variable}}}}}, and confirm the outcome.",
)

SIMILARITY_TEMPLATES: tuple[str, ...] = (
    "You should {goal}. Use {{{{{variable}}}}} when needed, keep the exchange natural, and confirm the result before moving on.",
    "{goal_cap}. Refer to {{{{{variable}}}}} where appropriate, stay natural, and confirm the outcome before continuing.",
    "Support a {category} {subcategory} interaction by helping the agent {goal}. Gather {{{{{variable}}}}}, restate the answer, and continue carefully.",
    "This prompt exists to {goal}. Ask for {{{{{variable}}}}}, reflect back what you heard, and proceed with a calm, clear tone.",
    "In a {category} {subcategory} workflow, {goal}. Use {{{{{variable}}}}} as the main slot, then confirm the next step explicitly.",
)


def benchmark_dataset_from_payload(payload: dict[str, object]) -> BenchmarkDataset:
    prompts_payload = payload.get("prompts", [])
    cluster_payload = payload.get("expected_duplicate_clusters", [])
    query_payload = payload.get("semantic_queries", [])
    metadata = payload.get("metadata", {})
    prompts = [PromptInput(**item) for item in prompts_payload]

    return BenchmarkDataset(
        prompts=prompts,
        expected_duplicate_clusters=[
            ExpectedDuplicateCluster(
                family_id=item["family_id"],
                prompt_ids=tuple(item["prompt_ids"]),
            )
            for item in cluster_payload
        ],
        semantic_queries=[
            SemanticBenchmarkQuery(
                query=item["query"],
                expected_prompt_ids=tuple(item["expected_prompt_ids"]),
            )
            for item in query_payload
        ],
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _build_family_specs(
    *,
    category_count: int,
    subcategories_per_category: int,
) -> list[FamilySpec]:
    selected_categories = CATEGORY_TAXONOMY[:category_count]
    family_specs: list[FamilySpec] = []

    for category_index, (category, subcategories) in enumerate(selected_categories):
        for subcategory_index, (subcategory, goal, variable, query) in enumerate(subcategories[:subcategories_per_category]):
            layer = LAYER_SEQUENCE[(category_index * subcategories_per_category + subcategory_index) % len(LAYER_SEQUENCE)]
            family_specs.append(
                FamilySpec(
                    category=category,
                    subcategory=subcategory,
                    goal=goal,
                    variable=variable,
                    query=query,
                    layer=layer,
                )
            )

    return family_specs


def _build_filler_prompt(family: FamilySpec, *, prompt_number: int) -> PromptInput:
    template = FILLER_TEMPLATES[prompt_number % len(FILLER_TEMPLATES)]
    return PromptInput(
        prompt_id=f"{family.family_id}.workflow_{prompt_number + 1:02d}",
        category=family.category,
        layer=family.layer,
        name=f"{family.display_name} Workflow {prompt_number + 1}",
        content=template.format(
            category=family.category.replace("_", " "),
            subcategory=family.subcategory.replace("_", " "),
            goal=family.goal,
            variable=family.variable,
        ),
    )


def _build_similarity_prompts(family: FamilySpec) -> list[PromptInput]:
    prompts: list[PromptInput] = []
    for index, template in enumerate(SIMILARITY_TEMPLATES):
        prompts.append(
            PromptInput(
                prompt_id=f"{family.family_id}.similar_{index + 1}",
                category=family.category,
                layer=family.layer,
                name=f"{family.display_name} Similar {index + 1}",
                content=template.format(
                    category=family.category.replace("_", " "),
                    subcategory=family.subcategory.replace("_", " "),
                    goal=family.goal,
                    goal_cap=family.goal[:1].upper() + family.goal[1:],
                    variable=family.variable,
                ),
            )
        )
    return prompts
def generate_benchmark_dataset(
    total_prompts: int,
    *,
    seed: int = 7,
    category_count: int = 20,
    subcategories_per_category: int = 4,
    seeded_similarity_prompt_count: int = 250,
) -> BenchmarkDataset:
    if total_prompts < 100:
        raise ValueError("total_prompts must be at least 100 for the taxonomy benchmark profile")
    if category_count < 1 or category_count > len(CATEGORY_TAXONOMY):
        raise ValueError("category_count is out of range")
    if subcategories_per_category < 1 or subcategories_per_category > 4:
        raise ValueError("subcategories_per_category must be between 1 and 4")
    if seeded_similarity_prompt_count % len(SIMILARITY_TEMPLATES) != 0:
        raise ValueError("seeded_similarity_prompt_count must be divisible by the duplicate cluster size")

    rng = Random(seed)
    family_specs = _build_family_specs(
        category_count=category_count,
        subcategories_per_category=subcategories_per_category,
    )
    family_count = len(family_specs)
    duplicate_cluster_size = len(SIMILARITY_TEMPLATES)
    duplicate_cluster_count = seeded_similarity_prompt_count // duplicate_cluster_size

    if duplicate_cluster_count > family_count:
        raise ValueError("Not enough families to seed the requested number of similarity prompts")
    if total_prompts <= seeded_similarity_prompt_count:
        raise ValueError("total_prompts must be greater than seeded_similarity_prompt_count")

    similarity_families = {
        family.family_id: family
        for family in rng.sample(family_specs, duplicate_cluster_count)
    }
    filler_prompt_count = total_prompts - seeded_similarity_prompt_count
    filler_base, filler_remainder = divmod(filler_prompt_count, family_count)

    prompts: list[PromptInput] = []
    expected_duplicate_clusters: list[ExpectedDuplicateCluster] = []
    semantic_queries: list[SemanticBenchmarkQuery] = []

    for family_index, family in enumerate(family_specs):
        family_filler_count = filler_base + (1 if family_index < filler_remainder else 0)
        for prompt_number in range(family_filler_count):
            prompts.append(_build_filler_prompt(family, prompt_number=prompt_number))

        if family.family_id in similarity_families:
            cluster_prompts = _build_similarity_prompts(family)
            prompts.extend(cluster_prompts)
            expected_duplicate_clusters.append(
                ExpectedDuplicateCluster(
                    family_id=family.family_id,
                    prompt_ids=tuple(prompt.prompt_id for prompt in cluster_prompts),
                )
            )
            semantic_queries.append(
                SemanticBenchmarkQuery(
                    query=family.query,
                    expected_prompt_ids=tuple(prompt.prompt_id for prompt in cluster_prompts),
                )
            )

    prompts = prompts[:total_prompts]
    layer_counts: dict[str, int] = {}
    for prompt in prompts:
        layer_counts[prompt.layer] = layer_counts.get(prompt.layer, 0) + 1

    metadata = {
        "profile": "taxonomy_balanced_v2",
        "seed": seed,
        "category_count": category_count,
        "subcategories_per_category": subcategories_per_category,
        "family_count": family_count,
        "seeded_similarity_prompt_count": seeded_similarity_prompt_count,
        "duplicate_cluster_count": len(expected_duplicate_clusters),
        "layer_counts": layer_counts,
        "categories": {
            category: [subcategory for subcategory, _, _, _ in subcategories[:subcategories_per_category]]
            for category, subcategories in CATEGORY_TAXONOMY[:category_count]
        },
    }

    return BenchmarkDataset(
        prompts=prompts,
        expected_duplicate_clusters=expected_duplicate_clusters,
        semantic_queries=semantic_queries,
        metadata=metadata,
    )


def summarize_cluster_alignment(
    *,
    actual_clusters: list[tuple[str, ...]] | list[list[str]],
    expected_clusters: list[tuple[str, ...]] | list[list[str]],
) -> dict[str, float | int]:
    normalized_actual = [
        tuple(sorted(dict.fromkeys(cluster)))
        for cluster in actual_clusters
        if len(set(cluster)) > 1
    ]
    normalized_expected = [
        tuple(sorted(dict.fromkeys(cluster)))
        for cluster in expected_clusters
        if len(set(cluster)) > 1
    ]

    actual_sets = [frozenset(cluster) for cluster in normalized_actual]
    expected_sets = [frozenset(cluster) for cluster in normalized_expected]

    actual_pairs = {
        tuple(sorted((cluster[index], cluster[other_index])))
        for cluster in normalized_actual
        for index in range(len(cluster))
        for other_index in range(index + 1, len(cluster))
    }
    expected_pairs = {
        tuple(sorted((cluster[index], cluster[other_index])))
        for cluster in normalized_expected
        for index in range(len(cluster))
        for other_index in range(index + 1, len(cluster))
    }

    true_positive_pairs = len(actual_pairs & expected_pairs)
    pairwise_precision = true_positive_pairs / len(actual_pairs) if actual_pairs else 0.0
    pairwise_recall = true_positive_pairs / len(expected_pairs) if expected_pairs else 0.0
    pairwise_f1 = (
        (2 * pairwise_precision * pairwise_recall) / (pairwise_precision + pairwise_recall)
        if (pairwise_precision + pairwise_recall) > 0.0
        else 0.0
    )
    subset_cluster_hits = sum(1 for expected in expected_sets if any(expected.issubset(actual) for actual in actual_sets))
    exact_cluster_hits = sum(1 for expected in expected_sets if expected in actual_sets)

    return {
        "expected_cluster_count": len(expected_sets),
        "actual_cluster_count": len(actual_sets),
        "subset_cluster_recall": round(subset_cluster_hits / len(expected_sets), 3) if expected_sets else 0.0,
        "exact_cluster_recall": round(exact_cluster_hits / len(expected_sets), 3) if expected_sets else 0.0,
        "pairwise_precision": round(pairwise_precision, 3),
        "pairwise_recall": round(pairwise_recall, 3),
        "pairwise_f1": round(pairwise_f1, 3),
    }


def summarize_durations(values_ms: list[float]) -> dict[str, float | int]:
    if not values_ms:
        return {
            "count": 0,
            "min_ms": 0.0,
            "avg_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
            "max_ms": 0.0,
        }

    ordered = sorted(values_ms)

    def percentile(percent: float) -> float:
        index = max(0, ceil((percent / 100.0) * len(ordered)) - 1)
        return float(ordered[index])

    return {
        "count": len(ordered),
        "min_ms": float(ordered[0]),
        "avg_ms": float(mean(ordered)),
        "p50_ms": percentile(50),
        "p95_ms": percentile(95),
        "max_ms": float(ordered[-1]),
    }
