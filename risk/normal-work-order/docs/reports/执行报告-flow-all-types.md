=== flow: risk-normal-work-order-all-types  run_id=0801111836  steps=35 ===

[other_tpl_save] POST https://test-risk.inshopline.com/mapi/cs/issue/config/save  [OTHER] 建专属模板
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[other_tpl_find] POST https://test-risk.inshopline.com/mapi/cs/issue/config/list  [OTHER] list 查回 configId
  -> 200  {"code":"SUCCESS","message":"","data":{"list":[{"issueConfigId":"821","issueConfigName":"[FLOW]TPL_OTHER_0801111836","subIssueType":"OTHER","opTime":1785554318894,"creatorId":"253","creator":"liyanda"
    ↳ extract other_tpl_id = 821
    ✓ status=200
    ✓ $.code=SUCCESS

[other_wo_save] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/save  [OTHER] 用模板+真实主键建工单
  -> 200  {"code":"SUCCESS","message":"","data":6161}
    ↳ extract other_wo_id = 6161
    ✓ status=200
    ✓ $.code=SUCCESS
    ✓ $.data exists=True

[other_wo_detail] GET https://test-risk.inshopline.com/mapi/cs/issue/normal/6161  [OTHER] 详情取字符串 issueId
  -> 200  {"code":"SUCCESS","message":"","data":{"issueId":"6161","issueName":"[FLOW]WO_OTHER_0801111836","approvalConfig":[{"step":1,"type":"SINGLE","approvalList":["253"],"approvalNameList":["liyanda"]}],"can
    ↳ extract other_wo_id = 6161
    ✓ status=200
    ✓ $.code=SUCCESS

[other_approve] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/approve  [OTHER] 审批通过→完结(名单类触发同步)
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[other_wo_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/base/6161  [OTHER] 清理工单
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[other_tpl_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/config/821  [OTHER] 清理模板
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[apply_tpl_save] POST https://test-risk.inshopline.com/mapi/cs/issue/config/save  [NAME_LIST_APPLY] 建专属模板
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[apply_tpl_find] POST https://test-risk.inshopline.com/mapi/cs/issue/config/list  [NAME_LIST_APPLY] list 查回 configId
  -> 200  {"code":"SUCCESS","message":"","data":{"list":[{"issueConfigId":"822","issueConfigName":"[FLOW]TPL_NAME_LIST_APPLY_0801111836","subIssueType":"NAME_LIST_APPLY","opTime":1785554321311,"creatorId":"253"
    ↳ extract apply_tpl_id = 822
    ✓ status=200
    ✓ $.code=SUCCESS

[apply_wo_save] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/save  [NAME_LIST_APPLY] 用模板+真实主键建工单
  -> 200  {"code":"SUCCESS","message":"","data":6162}
    ↳ extract apply_wo_id = 6162
    ✓ status=200
    ✓ $.code=SUCCESS
    ✓ $.data exists=True

[apply_wo_detail] GET https://test-risk.inshopline.com/mapi/cs/issue/normal/6162  [NAME_LIST_APPLY] 详情取字符串 issueId
  -> 200  {"code":"SUCCESS","message":"","data":{"issueId":"6162","issueName":"[FLOW]WO_NAME_LIST_APPLY_0801111836","approvalConfig":[{"step":1,"type":"SINGLE","approvalList":["253"],"approvalNameList":["liyand
    ↳ extract apply_wo_id = 6162
    ✓ status=200
    ✓ $.code=SUCCESS

[apply_approve] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/approve  [NAME_LIST_APPLY] 审批通过→完结(名单类触发同步)
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[apply_wo_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/base/6162  [NAME_LIST_APPLY] 清理工单
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[apply_tpl_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/config/822  [NAME_LIST_APPLY] 清理模板
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[delete_tpl_save] POST https://test-risk.inshopline.com/mapi/cs/issue/config/save  [NAME_LIST_DELETE] 建专属模板
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[delete_tpl_find] POST https://test-risk.inshopline.com/mapi/cs/issue/config/list  [NAME_LIST_DELETE] list 查回 configId
  -> 200  {"code":"SUCCESS","message":"","data":{"list":[{"issueConfigId":"823","issueConfigName":"[FLOW]TPL_NAME_LIST_DELETE_0801111836","subIssueType":"NAME_LIST_DELETE","opTime":1785554322820,"creatorId":"25
    ↳ extract delete_tpl_id = 823
    ✓ status=200
    ✓ $.code=SUCCESS

[delete_wo_save] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/save  [NAME_LIST_DELETE] 用模板+真实主键建工单
  -> 200  {"code":"SUCCESS","message":"","data":6163}
    ↳ extract delete_wo_id = 6163
    ✓ status=200
    ✓ $.code=SUCCESS
    ✓ $.data exists=True

[delete_wo_detail] GET https://test-risk.inshopline.com/mapi/cs/issue/normal/6163  [NAME_LIST_DELETE] 详情取字符串 issueId
  -> 200  {"code":"SUCCESS","message":"","data":{"issueId":"6163","issueName":"[FLOW]WO_NAME_LIST_DELETE_0801111836","approvalConfig":[{"step":1,"type":"SINGLE","approvalList":["253"],"approvalNameList":["liyan
    ↳ extract delete_wo_id = 6163
    ✓ status=200
    ✓ $.code=SUCCESS

[delete_approve] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/approve  [NAME_LIST_DELETE] 审批通过→完结(名单类触发同步)
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[delete_wo_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/base/6163  [NAME_LIST_DELETE] 清理工单
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[delete_tpl_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/config/823  [NAME_LIST_DELETE] 清理模板
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[onboard_tpl_save] POST https://test-risk.inshopline.com/mapi/cs/issue/config/save  [MERCHANT_ONBOARDING] 建专属模板
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[onboard_tpl_find] POST https://test-risk.inshopline.com/mapi/cs/issue/config/list  [MERCHANT_ONBOARDING] list 查回 configId
  -> 200  {"code":"SUCCESS","message":"","data":{"list":[{"issueConfigId":"824","issueConfigName":"[FLOW]TPL_MERCHANT_ONBOARDING_0801111836","subIssueType":"MERCHANT_ONBOARDING","opTime":1785554324315,"creatorI
    ↳ extract onboard_tpl_id = 824
    ✓ status=200
    ✓ $.code=SUCCESS

[onboard_wo_save] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/save  [MERCHANT_ONBOARDING] 用模板+真实主键建工单
  -> 200  {"code":"SUCCESS","message":"","data":6164}
    ↳ extract onboard_wo_id = 6164
    ✓ status=200
    ✓ $.code=SUCCESS
    ✓ $.data exists=True

[onboard_wo_detail] GET https://test-risk.inshopline.com/mapi/cs/issue/normal/6164  [MERCHANT_ONBOARDING] 详情取字符串 issueId
  -> 200  {"code":"SUCCESS","message":"","data":{"issueId":"6164","issueName":"[FLOW]WO_MERCHANT_ONBOARDING_0801111836","approvalConfig":[{"step":1,"type":"SINGLE","approvalList":["253"],"approvalNameList":["li
    ↳ extract onboard_wo_id = 6164
    ✓ status=200
    ✓ $.code=SUCCESS

[onboard_approve] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/approve  [MERCHANT_ONBOARDING] 审批通过→完结(名单类触发同步)
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[onboard_wo_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/base/6164  [MERCHANT_ONBOARDING] 清理工单
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[onboard_tpl_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/config/824  [MERCHANT_ONBOARDING] 清理模板
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[brand_tpl_save] POST https://test-risk.inshopline.com/mapi/cs/issue/config/save  [BRAND_PROTECTION] 建专属模板
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[brand_tpl_find] POST https://test-risk.inshopline.com/mapi/cs/issue/config/list  [BRAND_PROTECTION] list 查回 configId
  -> 200  {"code":"SUCCESS","message":"","data":{"list":[{"issueConfigId":"825","issueConfigName":"[FLOW]TPL_BRAND_PROTECTION_0801111836","subIssueType":"BRAND_PROTECTION","opTime":1785554325811,"creatorId":"25
    ↳ extract brand_tpl_id = 825
    ✓ status=200
    ✓ $.code=SUCCESS

[brand_wo_save] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/save  [BRAND_PROTECTION] 用模板+真实主键建工单
  -> 200  {"code":"SUCCESS","message":"","data":6165}
    ↳ extract brand_wo_id = 6165
    ✓ status=200
    ✓ $.code=SUCCESS
    ✓ $.data exists=True

[brand_wo_detail] GET https://test-risk.inshopline.com/mapi/cs/issue/normal/6165  [BRAND_PROTECTION] 详情取字符串 issueId
  -> 200  {"code":"SUCCESS","message":"","data":{"issueId":"6165","issueName":"[FLOW]WO_BRAND_PROTECTION_0801111836","approvalConfig":[{"step":1,"type":"SINGLE","approvalList":["253"],"approvalNameList":["liyan
    ↳ extract brand_wo_id = 6165
    ✓ status=200
    ✓ $.code=SUCCESS

[brand_approve] POST https://test-risk.inshopline.com/mapi/cs/issue/normal/approve  [BRAND_PROTECTION] 审批通过→完结(名单类触发同步)
  -> 200  {"code":"SUCCESS","message":"","data":true}
    ✓ status=200
    ✓ $.code=SUCCESS

[brand_wo_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/base/6165  [BRAND_PROTECTION] 清理工单
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

[brand_tpl_del] DELETE https://test-risk.inshopline.com/mapi/cs/issue/config/825  [BRAND_PROTECTION] 清理模板
  -> 200  {"code":"SUCCESS","message":"","data":null}
    ✓ status=200
    ✓ $.code=SUCCESS

=== 结果: 35 PASS / 0 FAIL ===
  PASS  other_tpl_save 
  PASS  other_tpl_find 
  PASS  other_wo_save 
  PASS  other_wo_detail 
  PASS  other_approve 
  PASS  other_wo_del 
  PASS  other_tpl_del 
  PASS  apply_tpl_save 
  PASS  apply_tpl_find 
  PASS  apply_wo_save 
  PASS  apply_wo_detail 
  PASS  apply_approve 
  PASS  apply_wo_del 
  PASS  apply_tpl_del 
  PASS  delete_tpl_save 
  PASS  delete_tpl_find 
  PASS  delete_wo_save 
  PASS  delete_wo_detail 
  PASS  delete_approve 
  PASS  delete_wo_del 
  PASS  delete_tpl_del 
  PASS  onboard_tpl_save 
  PASS  onboard_tpl_find 
  PASS  onboard_wo_save 
  PASS  onboard_wo_detail 
  PASS  onboard_approve 
  PASS  onboard_wo_del 
  PASS  onboard_tpl_del 
  PASS  brand_tpl_save 
  PASS  brand_tpl_find 
  PASS  brand_wo_save 
  PASS  brand_wo_detail 
  PASS  brand_approve 
  PASS  brand_wo_del 
  PASS  brand_tpl_del 
