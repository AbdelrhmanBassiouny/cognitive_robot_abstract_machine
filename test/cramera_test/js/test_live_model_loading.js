'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const ScenePanelFunctions = require('./scene_panel_functions');

// %% a model loaded after the newest live state
class SceneLoading extends ScenePanelFunctions {
  constructor(lastSeq) {
    super({
      SCENE: null, playbackSpeedMultiplier: 1, statusEl: null, linkToPart: {},
      models: [], robotModel: null, needsRender: false, sceneBase: '',
      worldRoot: {add() {}}, manager: {}, lastSeq: lastSeq,
      setTimeout() {},
    });
    this.scope.makeUrdfLoader = () => ({load(url, loaded) { loaded({}); }});
    this.scope.refreshFrameAxes = () => {};
    this.scope.addObject = () => {};
    this.scope.buildPlaceTargetMarker = () => {};
  }
}

test('a model that finishes loading takes the newest live state on the next poll', () => {
  const loading = new SceneLoading(2323);

  loading.scope.loadScene({name: 'live', models: [{name: 'tracy', urdf: 'tracy.urdf', robot: true}]});

  assert.notStrictEqual(loading.scope.lastSeq, 2323);
});
