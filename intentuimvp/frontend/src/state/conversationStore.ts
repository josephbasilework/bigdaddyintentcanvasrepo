import { create } from 'zustand';

/**
 * Conversation scope defines what context is active for agent interaction.
 * When a node is selected, conversations are scoped to that node.
 */
export type ConversationScope =
  | { type: 'global' }
  | { type: 'node'; nodeId: string; nodeTitle: string; hasContent: boolean };

/**
 * State for managing conversation scope and node context.
 * This is separate from canvasStore to avoid polluting undo/redo history.
 */
interface ConversationState {
  /** Current conversation scope (global or node-specific) */
  scope: ConversationScope;
  /** Whether the context banner is manually dismissed (resets on scope change) */
  contextBannerDismissed: boolean;
  
  /** Set scope to a specific node */
  setNodeScope: (nodeId: string, nodeTitle: string, hasContent: boolean) => void;
  /** Set scope to global (no node context) */
  setGlobalScope: () => void;
  /** Dismiss the context banner temporarily */
  dismissContextBanner: () => void;
  /** Check if we're in a node-scoped context */
  isNodeScoped: () => boolean;
  /** Get the current node ID if scoped to a node */
  getNodeId: () => string | null;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  scope: { type: 'global' },
  contextBannerDismissed: false,

  setNodeScope: (nodeId, nodeTitle, hasContent) => {
    set({
      scope: { type: 'node', nodeId, nodeTitle, hasContent },
      contextBannerDismissed: false,
    });
  },

  setGlobalScope: () => {
    set({
      scope: { type: 'global' },
      contextBannerDismissed: false,
    });
  },

  dismissContextBanner: () => {
    set({ contextBannerDismissed: true });
  },

  isNodeScoped: () => {
    return get().scope.type === 'node';
  },

  getNodeId: () => {
    const scope = get().scope;
    return scope.type === 'node' ? scope.nodeId : null;
  },
}));
