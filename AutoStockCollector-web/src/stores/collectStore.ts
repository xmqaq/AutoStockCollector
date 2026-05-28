import { create } from 'zustand';
import type { TaskProgress } from '@/types';

interface CollectStore {
  tasks: TaskProgress[];
  allDone: boolean;
  setTasks: (tasks: TaskProgress[], allDone: boolean) => void;
  updateTask: (type: string, updates: Partial<TaskProgress>) => void;
}

export const useCollectStore = create<CollectStore>((set) => ({
  tasks: [],
  allDone: false,
  setTasks: (tasks, allDone) => set({ tasks, allDone }),
  updateTask: (type, updates) =>
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.type === type ? { ...task, ...updates } : task
      ),
    })),
}));