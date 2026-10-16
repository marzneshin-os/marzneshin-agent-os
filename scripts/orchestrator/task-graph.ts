import { TaskBrief, TaskResult } from "./schemas.js";

export interface TaskStage {
  stageIndex: number;
  tasks: TaskBrief[];
}

export class TaskGraph {
  private tasks: Map<string, TaskBrief> = new Map();

  constructor(taskList: TaskBrief[]) {
    for (const t of taskList) {
      this.tasks.set(t.id, t);
    }
    this.validateGraph();
  }

  private validateGraph(): void {
    for (const [id, task] of this.tasks.entries()) {
      if (task.dependsOn) {
        for (const depId of task.dependsOn) {
          if (!this.tasks.has(depId)) {
            throw new Error(`Task ${id} depends on nonexistent task ${depId}`);
          }
          if (depId === id) {
            throw new Error(`Task ${id} has a self-dependency`);
          }
        }
      }
    }
  }

  public computeStages(): TaskStage[] {
    const inDegree: Map<string, number> = new Map();
    const dependents: Map<string, string[]> = new Map();

    for (const [id, task] of this.tasks.entries()) {
      const deps = task.dependsOn ?? [];
      inDegree.set(id, deps.length);
      for (const d of deps) {
        if (!dependents.has(d)) dependents.set(d, []);
        dependents.get(d)!.push(id);
      }
    }

    const stages: TaskStage[] = [];
    let currentBatch = Array.from(this.tasks.keys()).filter((id) => inDegree.get(id) === 0);
    let stageIndex = 0;
    const processed = new Set<string>();

    while (currentBatch.length > 0) {
      stages.push({
        stageIndex: stageIndex++,
        tasks: currentBatch.map((id) => this.tasks.get(id)!),
      });

      const nextBatch: string[] = [];
      for (const id of currentBatch) {
        processed.add(id);
        const children = dependents.get(id) ?? [];
        for (const childId of children) {
          const newDeg = (inDegree.get(childId) ?? 1) - 1;
          inDegree.set(childId, newDeg);
          if (newDeg === 0) {
            nextBatch.push(childId);
          }
        }
      }
      currentBatch = nextBatch;
    }

    if (processed.size !== this.tasks.size) {
      throw new Error("Cycle detected in task dependency graph!");
    }

    return stages;
  }
}
