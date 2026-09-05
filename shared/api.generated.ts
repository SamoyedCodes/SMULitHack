export interface paths {
    "/api/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Disabled */
        post: operations["disabled_api_batches_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batch_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Batch */
        get: operations["batch_api_batches__batch_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/demo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Disabled */
        post: operations["disabled_api_demo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Document */
        get: operations["document_api_documents__document_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/original": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Disabled */
        get: operations["disabled_api_documents__document_id__original_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/pages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Disabled */
        get: operations["disabled_api_documents__document_id__pages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/pages/{number}/image": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Disabled */
        get: operations["disabled_api_documents__document_id__pages__number__image_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Jobs */
        get: operations["jobs_api_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/portfolio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Portfolio */
        get: operations["portfolio_api_portfolio_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Disabled */
        post: operations["disabled_api_retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/review/{issue_id}/brief": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Disabled */
        get: operations["disabled_api_review__issue_id__brief_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/settings/sme": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Set Sme */
        post: operations["set_sme_api_settings_sme_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Capabilities */
        Capabilities: {
            /**
             * Conflicts
             * @default false
             */
            conflicts: boolean;
            /**
             * Deadlines
             * @default false
             */
            deadlines: boolean;
            /**
             * Extraction
             * @default false
             */
            extraction: boolean;
            /**
             * Handoff
             * @default false
             */
            handoff: boolean;
            /**
             * Ingestion
             * @default false
             */
            ingestion: boolean;
            /**
             * Sample Workspace
             * @default false
             */
            sample_workspace: boolean;
        };
        /** Citation */
        Citation: {
            /** Document Id */
            document_id: string;
            /** Quote */
            quote: string;
            /** Span Ids */
            span_ids: string[];
        };
        /** CommercialProvision */
        CommercialProvision: {
            /** Activity */
            activity: string;
            /** Beneficiary */
            beneficiary: string | null;
            /** Channel */
            channel: string | null;
            /** Citations */
            citations: components["schemas"]["Citation"][];
            /** Customers */
            customers: string | null;
            /** Ends On */
            ends_on: string | null;
            /** Exceptions */
            exceptions: string[];
            /** Exclusive */
            exclusive: boolean | null;
            /** Grantor */
            grantor: string | null;
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "distribution" | "other" | "unknown";
            /** Missing Context */
            missing_context: string[];
            /** Product */
            product: string | null;
            /** Starts On */
            starts_on: string | null;
            /** Territory */
            territory: string | null;
        };
        /** ConflictAssessment */
        ConflictAssessment: {
            /**
             * Confidence
             * @enum {string}
             */
            confidence: "medium" | "low";
            /** Confidence Reason */
            confidence_reason: string;
            /** Documents */
            documents: string[];
            /** Evidence */
            evidence: components["schemas"]["Evidence"][];
            /** Exceptions */
            exceptions: string[];
            /** Explanation */
            explanation: string;
            /** Id */
            id: string;
            /** Lawyer Question */
            lawyer_question: string;
            /** Missing Facts */
            missing_facts: string[];
            /**
             * Mode
             * @default live
             * @enum {string}
             */
            mode: "live" | "sample";
            /**
             * Provenance
             * @enum {string}
             */
            provenance: "inferred" | "unresolved";
            /** Scope Comparison */
            scope_comparison: {
                [key: string]: string;
            };
            /**
             * Status
             * @enum {string}
             */
            status: "potential_conflict" | "no_conflict_identified_for_this_rule" | "insufficient_evidence";
        };
        /** DatabaseStatus */
        DatabaseStatus: {
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "unavailable";
        };
        /** DeadlineRule */
        DeadlineRule: {
            /**
             * Action
             * @enum {string}
             */
            action: "notice_received" | "notice_sent" | "payment_due" | "review" | "expiry";
            /** Citations */
            citations: components["schemas"]["Citation"][];
            /** Conditions */
            conditions: string[];
            /**
             * Direction
             * @default before
             * @enum {string}
             */
            direction: "before" | "after";
            /** Earliest Offset */
            earliest_offset: number | null;
            /** Event Date */
            event_date: string | null;
            /**
             * Event Type
             * @enum {string}
             */
            event_type: "expiry" | "renewal" | "payment" | "termination" | "other";
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Missing Inputs */
            missing_inputs: string[];
            /**
             * Month End Rule
             * @default unspecified
             * @enum {string}
             */
            month_end_rule: "last_day" | "unspecified";
            /** Offset */
            offset: number | null;
            /** Recurrence Months */
            recurrence_months: number | null;
            /** Trigger */
            trigger: string;
            /**
             * Unit
             * @default calendar_days
             * @enum {string}
             */
            unit: "calendar_days" | "calendar_months" | "business_days" | "unknown";
        };
        /** Document */
        Document: {
            /** Created At */
            created_at: string;
            /** Error */
            error: string | null;
            /** Filename */
            filename: string;
            /** Findings */
            findings: components["schemas"]["Finding"][];
            /**
             * Has Ocr
             * @default false
             */
            has_ocr: boolean;
            /** Id */
            id: string;
            /** Issues */
            issues: components["schemas"]["ReviewIssue"][];
            /**
             * Mode
             * @enum {string}
             */
            mode: "live" | "sample";
            /** Model */
            model: string;
            /**
             * Page Count
             * @default 0
             */
            page_count: number;
            /**
             * Pages Analyzed
             * @default 0
             */
            pages_analyzed: number;
            /**
             * Pages Read
             * @default 0
             */
            pages_read: number;
            /**
             * Pagination
             * @default original
             */
            pagination: string;
            /** Parties */
            parties: string[];
            /** Provisions */
            provisions: components["schemas"]["CommercialProvision"][];
            /** Reviews */
            reviews: components["schemas"]["Verdict"][];
            /** Rules */
            rules: components["schemas"]["DeadlineRule"][];
            /** Sha256 */
            sha256: string;
            /**
             * Stage
             * @default Waiting to process
             */
            stage: string;
            /**
             * Status
             * @default queued
             */
            status: string;
            /** Title */
            title: string;
            /** Version */
            version: string;
            /** Warnings */
            warnings: string[];
        };
        /** ErrorDetail */
        ErrorDetail: {
            /** Code */
            code: string;
            /** Details */
            details: string[];
            /** Message */
            message: string;
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ErrorDetail"];
        };
        /** Event */
        Event: {
            /** Action */
            action: string;
            /** Action Date */
            action_date: string | null;
            /** Assumptions */
            assumptions: string[];
            /**
             * Confidence
             * @enum {string}
             */
            confidence: "high" | "medium" | "low";
            /** Document Id */
            document_id: string;
            /** Event Date */
            event_date: string;
            /** Event Type */
            event_type: string;
            /** Evidence */
            evidence: components["schemas"]["Evidence"][];
            /** Formula */
            formula: string;
            /** Id */
            id: string;
            /** Label */
            label: string;
            /**
             * Provenance
             * @default calculated
             * @constant
             */
            provenance: "calculated";
            /** Window Start */
            window_start: string | null;
        };
        /** Evidence */
        Evidence: {
            /** Boxes */
            boxes: number[][];
            /** Clause */
            clause: string | null;
            /** Document Id */
            document_id: string;
            /** Ocr Confidence */
            ocr_confidence: number | null;
            /** Page */
            page: number;
            /** Quote */
            quote: string;
            /**
             * Source
             * @enum {string}
             */
            source: "native" | "ocr";
            /** Span Ids */
            span_ids: string[];
        };
        /**
         * FieldName
         * @enum {string}
         */
        FieldName: "parties" | "term" | "renewal" | "notice" | "termination" | "payments" | "liability" | "restrictions";
        /** Finding */
        Finding: {
            /** Conditions */
            conditions: string[];
            /**
             * Confidence
             * @enum {string}
             */
            confidence: "high" | "medium" | "low";
            /** Confidence Reason */
            confidence_reason: string;
            /** Evidence */
            evidence: components["schemas"]["Evidence"][];
            field: components["schemas"]["FieldName"];
            /** Id */
            id: string;
            /** Party */
            party: string | null;
            /**
             * Provenance
             * @enum {string}
             */
            provenance: "found" | "calculated" | "inferred" | "unresolved";
            /** Value */
            value: string | null;
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Api Version
             * @default 1
             * @constant
             */
            api_version: "1";
            capabilities: components["schemas"]["Capabilities"];
            database: components["schemas"]["DatabaseStatus"];
            /** Docx Available */
            docx_available: boolean;
            /**
             * Inference Notice
             * @default When analysis is enabled, extracted contract text is sent to Gemini. Original files and saved results stay local.
             */
            inference_notice: string;
            /** Key Configured */
            key_configured: boolean;
            limits: components["schemas"]["Limits"];
            /** Model */
            model: string;
            /**
             * Model Status
             * @enum {string}
             */
            model_status: "not_configured" | "configured_unverified";
            /** Ocr Available */
            ocr_available: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "degraded";
            /** Version */
            version: string;
            worker: components["schemas"]["WorkerStatus"];
        };
        /** Limits */
        Limits: {
            /**
             * Files Per Batch
             * @default 80
             */
            files_per_batch: number;
            /**
             * Megabytes Per File
             * @default 25
             */
            megabytes_per_file: number;
            /**
             * Pages Per File
             * @default 200
             */
            pages_per_file: number;
        };
        /** Page */
        Page: {
            /** Height */
            height: number;
            /** Number */
            number: number;
            /** Spans */
            spans: components["schemas"]["Span"][];
            /**
             * Status
             * @default read
             * @enum {string}
             */
            status: "read" | "unreadable" | "error";
            /** Warnings */
            warnings: string[];
            /** Width */
            width: number;
        };
        /** Portfolio */
        Portfolio: {
            /** As Of */
            as_of: string;
            /** Comparisons */
            comparisons: {
                [key: string]: number;
            };
            /** Conflicts */
            conflicts: components["schemas"]["ConflictAssessment"][];
            /** Coverage */
            coverage: {
                [key: string]: number;
            };
            /** Documents */
            documents: components["schemas"]["Document"][];
            /** Events */
            events: components["schemas"]["Event"][];
            /** Horizon End */
            horizon_end: string;
            /** Issues */
            issues: components["schemas"]["ReviewIssue"][];
            /** Mode */
            mode: string;
            /** Parties */
            parties: string[];
            /** Sme */
            sme: string | null;
        };
        /** ReviewIssue */
        ReviewIssue: {
            /** Document Ids */
            document_ids: string[];
            /** Established */
            established: string[];
            /** Evidence */
            evidence: components["schemas"]["Evidence"][];
            /** Id */
            id: string;
            /**
             * Kind
             * @default uncertainty
             */
            kind: string;
            /** Lawyer Question */
            lawyer_question: string;
            /** Missing Facts */
            missing_facts: string[];
            /**
             * Mode
             * @default live
             * @enum {string}
             */
            mode: "live" | "sample";
            /** Title */
            title: string;
            /**
             * Urgency
             * @default Review before relying on this provision.
             */
            urgency: string;
        };
        /** SmeSelection */
        "SmeSelection-Input": {
            /**
             * Mode
             * @default live
             * @enum {string}
             */
            mode: "live" | "sample";
            /** Name */
            name: string | null;
        };
        /** SmeSelection */
        "SmeSelection-Output": {
            /**
             * Mode
             * @default live
             * @enum {string}
             */
            mode: "live" | "sample";
            /** Name */
            name: string | null;
        };
        /** Span */
        Span: {
            /** Bbox */
            bbox: number[];
            /** Clause */
            clause: string | null;
            /** Document Id */
            document_id: string;
            /** Id */
            id: string;
            /** Ocr Confidence */
            ocr_confidence: number | null;
            /** Page */
            page: number;
            /**
             * Source
             * @enum {string}
             */
            source: "native" | "ocr";
            /** Text */
            text: string;
        };
        /** Verdict */
        Verdict: {
            /** Item Id */
            item_id: string;
            /** Missing Context */
            missing_context: string[];
            /** Reason */
            reason: string;
            /**
             * Status
             * @enum {string}
             */
            status: "supported" | "uncertain" | "rejected";
        };
        /** WorkerStatus */
        WorkerStatus: {
            /**
             * Enabled
             * @default false
             */
            enabled: boolean;
            /**
             * Running
             * @default false
             */
            running: boolean;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    disabled_api_batches_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Successful Response */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    batch_api_batches__batch_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batch_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disabled_api_demo_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Successful Response */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    document_api_documents__document_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Document"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disabled_api_documents__document_id__original_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disabled_api_documents__document_id__pages_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page"][];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disabled_api_documents__document_id__pages__number__image_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    jobs_api_jobs_get: {
        parameters: {
            query?: {
                mode?: "live" | "sample";
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    portfolio_api_portfolio_get: {
        parameters: {
            query?: {
                mode?: "live" | "sample";
                as_of?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Portfolio"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disabled_api_retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Successful Response */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    disabled_api_review__issue_id__brief_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    set_sme_api_settings_sme_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SmeSelection-Input"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SmeSelection-Output"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
