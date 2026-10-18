import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {insightSections, planExplanation, hypothesisCells} from '../src/analysisView.js';

const contract=JSON.parse(readFileSync(new URL('../../tests/data/analysis_contract.json',import.meta.url)));

test('hypothesis tables expose raw and adjusted probabilities without rounding tiny values to zero', () => {
  const cells = hypothesisCells({test:'ANOVA',p_value:1e-36,p_value_adjusted:2e-36,statistically_significant:true});
  assert.equal(cells[2],'1.000e-36'); assert.equal(cells[3],'2.000e-36');
  assert.equal(cells[4],'Significant');
  assert.equal(hypothesisCells({p_value:null})[2],'Unavailable');
});

test('completed backend results show all four insights and hypothesis rows', () => {
  const sections=insightSections(contract);
  assert.deepEqual(sections.map(s=>s.content),[
    'Sales total is 350.','East contributes 150.',
    'Sales increased across three months.','One significant difference was found.',
  ]);
  assert.equal(sections[3].data[0].p_value,0.01);
  assert.equal(planExplanation(contract),contract.analysis_plan.reasoning);
});

test('a skipped trend explains why and absent results have honest placeholders', () => {
  const sections=insightSections({trend_results:{available:false,reason:'No date column detected.'}});
  assert.equal(sections[2].content,'No date column detected.');
  assert.equal(sections[0].content,'KPI analysis not available.');
  assert.equal(planExplanation({}), '');
});
