import { describe, it, expect, beforeEach } from 'vitest';
import { useConversationStore } from './conversationStore';

describe('conversationStore', () => {
  beforeEach(() => {
    useConversationStore.setState({
      scope: { type: 'global' },
      contextBannerDismissed: false,
    });
  });

  it('should initialize with global scope', () => {
    const state = useConversationStore.getState();
    expect(state.scope).toEqual({ type: 'global' });
    expect(state.contextBannerDismissed).toBe(false);
  });

  it('should set node scope with setNodeScope', () => {
    const { setNodeScope } = useConversationStore.getState();
    
    setNodeScope('node-123', 'Test Node', true);
    
    const state = useConversationStore.getState();
    expect(state.scope).toEqual({
      type: 'node',
      nodeId: 'node-123',
      nodeTitle: 'Test Node',
      hasContent: true,
    });
    expect(state.contextBannerDismissed).toBe(false);
  });

  it('should set global scope with setGlobalScope', () => {
    const { setNodeScope, setGlobalScope } = useConversationStore.getState();
    
    setNodeScope('node-123', 'Test Node', true);
    setGlobalScope();
    
    const state = useConversationStore.getState();
    expect(state.scope).toEqual({ type: 'global' });
  });

  it('should reset banner dismissed state on scope change', () => {
    const { setNodeScope, dismissContextBanner, setGlobalScope } = useConversationStore.getState();
    
    setNodeScope('node-123', 'Test Node', true);
    dismissContextBanner();
    expect(useConversationStore.getState().contextBannerDismissed).toBe(true);
    
    setGlobalScope();
    expect(useConversationStore.getState().contextBannerDismissed).toBe(false);
  });

  it('should dismiss context banner', () => {
    const { dismissContextBanner } = useConversationStore.getState();
    
    dismissContextBanner();
    
    expect(useConversationStore.getState().contextBannerDismissed).toBe(true);
  });

  it('should check if node scoped with isNodeScoped', () => {
    const { isNodeScoped, setNodeScope, setGlobalScope } = useConversationStore.getState();
    
    expect(isNodeScoped()).toBe(false);
    
    setNodeScope('node-123', 'Test Node', false);
    expect(useConversationStore.getState().isNodeScoped()).toBe(true);
    
    setGlobalScope();
    expect(useConversationStore.getState().isNodeScoped()).toBe(false);
  });

  it('should get node ID with getNodeId', () => {
    const { getNodeId, setNodeScope, setGlobalScope } = useConversationStore.getState();
    
    expect(getNodeId()).toBeNull();
    
    setNodeScope('node-456', 'Another Node', true);
    expect(useConversationStore.getState().getNodeId()).toBe('node-456');
    
    setGlobalScope();
    expect(useConversationStore.getState().getNodeId()).toBeNull();
  });

  it('should handle node scope without content', () => {
    const { setNodeScope } = useConversationStore.getState();
    
    setNodeScope('node-789', 'Node Without Content', false);
    
    const state = useConversationStore.getState();
    expect(state.scope).toEqual({
      type: 'node',
      nodeId: 'node-789',
      nodeTitle: 'Node Without Content',
      hasContent: false,
    });
  });
});
