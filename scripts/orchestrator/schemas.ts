export type SpecialistRole =
  | "memory-architect"
  | "mcp-tool-builder"
  | "api-endpoint-builder"
  | "hook-specialist"
  | "test-engineer"
  | "consistency-guardian";

export interface SubagentConfig {
  name: string;
  description: string;
  model: string;
  instructions: string;
}

export type ContextIsolationMode = "worktree" | "sandbox" | "direct";

export interface TaskBrief {
  id: string;
  title: string;
  specialist: SpecialistRole;
  prompt: string;
  dependsOn?: string[];
  filesToTouch?: string[];
  filesToRead?: string[];
  isolation?: ContextIsolationMode;
  timeoutMs?: number;
}

export interface TaskResult {
  taskId: string;
  specialist: SpecialistRole;
  status: "success" | "failed" | "skipped";
  durationMs: number;
  modifiedFiles: string[];
  summary: string;
  error?: string;
  worktreePath?: string;
  blastRadiusScore?: number;
  rollbackTriggered?: boolean;
  tierModel?: string;
}

export interface OrchestrationPlan {
  id: string;
  goal: string;
  tasks: TaskBrief[];
  createdAt: string;
}

export interface OrchestrationRunResult {
  id: string;
  goal: string;
  status: "completed" | "failed";
  startTime: string;
  endTime: string;
  totalDurationMs: number;
  taskResults: Record<string, TaskResult>;
  consistencyAudit: {
    passed: boolean;
    details: string;
  };
  rollbackDefense?: {
    evaluated: number;
    rollbacksPrevented: number;
    status: string;
  };
}
