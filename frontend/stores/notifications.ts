import { create } from "zustand";

export interface WsNotification {
  id: string;
  event: string;
  data: Record<string, unknown>;
  timestamp: string;
  read: boolean;
}

interface NotificationState {
  notifications: WsNotification[];
  unreadCount: number;
  addNotification: (event: string, data: Record<string, unknown>, timestamp: string) => void;
  markAllRead: () => void;
  markRead: (id: string) => void;
  clearAll: () => void;
  removeNotification: (id: string) => void;
}

let notifCounter = 0;

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,

  addNotification(event, data, timestamp) {
    const id = `notif-${Date.now()}-${++notifCounter}`;
    const notification: WsNotification = { id, event, data, timestamp, read: false };
    set((state) => ({
      notifications: [notification, ...state.notifications].slice(0, 100),
      unreadCount: state.unreadCount + 1,
    }));
  },

  markAllRead() {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }));
  },

  markRead(id) {
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
      unreadCount: Math.max(0, state.unreadCount - (state.notifications.find((n) => n.id === id && !n.read) ? 1 : 0)),
    }));
  },

  clearAll() {
    set({ notifications: [], unreadCount: 0 });
  },

  removeNotification(id) {
    const state = get();
    const target = state.notifications.find((n) => n.id === id);
    set({
      notifications: state.notifications.filter((n) => n.id !== id),
      unreadCount: target && !target.read ? state.unreadCount - 1 : state.unreadCount,
    });
  },
}));