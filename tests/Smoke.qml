import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import Quickshell.Io
import qs.Commons
import "AzureSql" as Desk

ShellRoot {
  id: test
  property int stage: 0
  property int ticks: 0
  property bool failed: false
  Desk.Controller { id: backend }
  Desk.Controller { id: isolated }
  FileView { id: failureMarker; path: Quickshell.env("SQL_TEST_FAILURE"); printErrors: false }
  Window {
    id: window
    visible: true; width: 1120; height: 760; color: Color.background
    Desk.PanelContent { id: panel; controller: backend; anchors.fill: parent; anchors.margins: 12 }
    TestCase { id: driver; when: false; name: "AzureDeskRegressions" }
  }
  function all(o) {
    var out=[],seen=[];
    function visit(x) {
      if (!x || seen.indexOf(x)>=0) return; seen.push(x);out.push(x);
      var list=x.children||[]; for(var i=0;i<list.length;i++)visit(list[i]);
      list=x.data||[]; for(var j=0;j<list.length;j++)visit(list[j]);
    }
    visit(o);return out;
  }
  function find(pred) { return all(window.contentItem).filter(pred)[0]; }
  function named(name) { return find(function(o){return o.objectName===name;}); }
  function check(ok, message) { if(!ok) { console.error("QML_CHECK_FAILED",message);failed=true;Qt.quit(); } return ok; }
  function visibleInPane(name) {
    var item=named(name),pane=named("filtersPane"),y=item.mapToItem(pane,0,0).y;
    return y>=0 && y+item.height<=pane.height;
  }
  Component.onCompleted: {
    Color.background="#111923";Color.foreground="#e6edf3";Color.accent="#63b3ed";Color.urgent="#f28b82";
    backend.panelOpened();
  }
  Timer {
    interval: 50; running: true; repeat: true
    onTriggered: {
      test.ticks++;
      if(test.ticks>1500) { test.check(false,"Timed out at stage "+test.stage+": "+backend.error+" "+backend.viewError);return; }
      if(backend.busy||backend.pageLoading||backend.viewsBusy||backend.filtersPending||test.failed)return;
      if(test.stage===0 && backend.databaseRows.length) {
        if(!test.check(backend.databaseRows.length===25 && backend.totalCount===20002 && backend.pageCount===801,"25-row paging failed"))return;
        if(!test.check(!test.named("azureSignInButton").visible,"Sign in shown while authenticated"))return;
        if(!test.check(test.visibleInPane("databaseNameFilter") && test.visibleInPane("saveViewButton") && test.visibleInPane("savedViewSelector"),"Primary controls below viewport"))return;
        if(!test.check(test.named("filtersPane").x>test.named("databasePane").x,"Filter pane must remain on right"))return;
        if(!test.check(!test.named("identityControls").visible,"Identity controls must start collapsed"))return;
        test.named("identityToggleButton").clicked();
        if(!test.check(test.named("identityControls").visible,"Accounts toggle did not reveal controls"))return;
        panel.toggleDatabase(0);test.stage=1;
      } else if(test.stage===1 && backend.detail) {
        if(!test.check(backend.database.status==="Online" && backend.database.publicNetworkAccess==="Enabled" && backend.database.metrics.cpu_percent.value===18.4,"Fresh expanded state missing"))return;
        failureMarker.setText("changed");panel.toggleDatabase(0);panel.toggleDatabase(0);test.stage=2;
      } else if(test.stage===2 && backend.detail) {
        if(!test.check(backend.database.status==="Paused" && backend.database.publicNetworkAccess==="Disabled","Expansion did not refresh status/security"))return;
        failureMarker.setText("");panel.toggleDatabase(0);panel.toggleDatabase(0);panel.toggleDatabase(1);test.stage=3;
      } else if(test.stage===3 && backend.detail) {
        if(!test.check(backend.database.name==="integration-tests" && backend.detail.id===backend.database.id,"Obsolete selection won race"))return;
        backend.goToPage(800);test.stage=4;
      } else if(test.stage===4 && backend.databaseRows.length) {
        if(!test.check(backend.databaseRows.length===2 && backend.databaseRows[0].name==="tenant-19998","Last page incorrect"))return;
        if(!test.check(!test.named("nextPageButton").enabled,"Next enabled past last page"))return;
        backend.setFilter("filter","tenant-00077");test.stage=5;
      } else if(test.stage===5 && backend.databaseRows.length) {
        if(!test.check(backend.pageIndex===0 && backend.totalCount===1 && backend.databaseRows[0].name==="tenant-00077","Name filter must apply before paging"))return;
        backend.saveView("Production",backend.filters.filter,true,false);test.stage=6;
      } else if(test.stage===6 && backend.selectedViewId) {
        if(!test.check(backend.defaultViewId===backend.selectedViewId,"Default view was not saved"))return;
        backend.setFilter("filter","tenant-00078");test.stage=7;
      } else if(test.stage===7 && backend.databaseRows.length) {
        if(!test.check(backend.selectedViewId!=="" && backend.viewDirty,"Filter edits lost selected view identity"))return;
        backend.saveView("Production",backend.filters.filter,true,true);test.stage=8;
      } else if(test.stage===8 && !backend.viewDirty) {
        if(!test.check(backend.savedViews.length===1 && backend.defaultViewId===backend.selectedViewId,"View update lost default"))return;
        backend.panelClosed();test.named("saveViewButton").clicked();test.stage=9;
      } else if(test.stage===9) {
        var checkbox=test.named("saveAsDefault");
        if(!test.check(checkbox.checked && String(checkbox.contentItem.color)===String(Color.foreground),"Default checkbox state/contrast incorrect"))return;
        test.named("saveViewDialog").close();
        test.find(function(o){return o.label==="Service tiers" && o.clicked!==undefined;}).clicked();test.stage=10;
      } else if(test.stage===10) {
        driver.keyClick(Qt.Key_Down);driver.keyClick(Qt.Key_Down);driver.keyClick(Qt.Key_Return);
        if(!test.check(backend.filters.tiers.length===1 && backend.filters.tiers[0]==="BusinessCritical","Arrow navigation did not select second option"))return;
        driver.keyClick(Qt.Key_Space);
        if(!test.check(backend.filters.tiers.length===0,"Space did not toggle selected option"))return;
        var option=test.find(function(o){return o.text==="Basic" && o.checked!==undefined;});
        if(!test.check(option && String(option.background.color)===String(Color.background),"Dropdown background does not match theme"))return;
        driver.keyClick(Qt.Key_Tab);driver.keyClick(Qt.Key_Return);
        backend.filtersPending=false;
        backend.filters=Object.assign({},backend.emptyFilters(),{subscriptionIds:["sub-a"],serverIds:["/subscriptions/sub-a/server/a"]});
        backend.setFilter("subscriptionIds",["sub-b"],true);
        if(!test.check(backend.filters.serverIds.length===0,"Subscription retained incompatible server"))return;
        backend.filtersPending=false;backend.filters=backend.emptyFilters();window.width=800;window.height=540;test.stage=11;
      } else if(test.stage===11) {
        if(!test.check(test.visibleInPane("databaseNameFilter") && test.visibleInPane("savedViewSelector"),"Compact viewport hides primary controls"))return;
        // Drive controller replies without spawning a helper; ensure billing cannot suppress ARM.
        isolated.authenticated=true;isolated.authenticationKnown=true;isolated.activeRequest={kind:"catalog"};
        var row={id:backend.databaseRows[0].id,name:"Test",status:"Online",publicNetworkAccess:"Unknown",metrics:{}};
        isolated.applyReply({kind:"catalog",payload:{}},{rows:[row],totalCount:1,facets:{},warnings:[],rateLimited:true,retryAfterSec:900,throttleScope:"billing"});
        if(!test.check(!isolated.refreshThrottled && isolated.pendingRequest.kind==="live","Billing cooldown suppressed initial security check"))return;
        isolated.pendingRequest=null;isolated.backOff(900,"metrics");isolated.chooseDatabase(0);
        if(!test.check(isolated.pendingRequest.kind==="live" && isolated.pendingRequest.payload.skipMetrics && isolated.pendingRequest.payload.detailsId===row.id,"Expansion must request bounded ARM refresh during metrics cooldown"))return;
        isolated.filters=Object.assign({},isolated.emptyFilters(),{sortBy:"costDesc"});
        isolated.costRanking=Array.from({length:30},function(_,i){return {id:row.id+i,cost:{amount:30-i}};});
        isolated.rankingMonth=new Date().toISOString().slice(0,7);isolated.totalCount=30;isolated.panelActive=true;isolated.goToPage(1);
        if(!test.check(isolated.pendingRequest.kind==="catalog" && isolated.pendingRequest.payload.rankedIds.length===5,"Cost page discarded existing ranking"))return;
        isolated.panelClosed();
        if(!test.check(isolated.costRanking===null,"Ranking retained after panel close"))return;
        isolated.activeRequest=null;isolated.pendingRequest=null;
        backend.authenticated=false;backend.authenticationKnown=true;test.stage=12;
      } else if(test.stage===12) {
        if(!test.check(test.named("azureSignInButton").visible,"Sign in missing when logged out"))return;
        backend.authenticated=true;backend.panelActive=true;
        backend.setFilter("filter","tenant-000");backend.setFilter("sortBy","costDesc");test.stage=13;
      } else if(test.stage===13 && backend.costRanking) {
        if(!test.check(backend.costRanking.length===100 && backend.databaseRows[0].name==="tenant-00000","Cost ranking incorrect"))return;
        failureMarker.setText("billing-throttle");backend.goToPage(1);test.stage=14;
      } else if(test.stage===14 && backend.databaseRows.length) {
        if(!test.check(backend.databaseRows[0].name==="tenant-00025" && !backend.cooldowns.billing && backend.databaseRows[0].cost.amount>0,"Cost pagination repeated billing or lost costs"))return;
        failureMarker.setText("");backend.panelClosed();
        Color.background="#f7f7f7";Color.foreground="#17212b";Color.accent="#245a9a";
        test.named("saveViewButton").clicked();test.stage=15;
      } else if(test.stage===15) {
        var checkbox=test.named("saveAsDefault");
        if(!test.check(String(checkbox.contentItem.color)===String(Color.foreground) && String(checkbox.background.color)===String(Color.background),"Light theme checkbox contrast incorrect"))return;
        test.named("saveViewDialog").close();
        backend.panelActive=true;backend.switchDirectory(0);test.stage=16;
      } else if(test.stage===16 && backend.databaseRows.length) {
        if(!test.check(backend.tenantId==="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" && backend.subscriptionRows.length===1 && backend.subscriptionRows[0].id==="22222222-2222-4222-8222-222222222222","Directory switch crossed subscription boundary"))return;
        if(!test.check(backend.databaseRows[0].id.indexOf("/subscriptions/22222222-")===0 && backend.filters.subscriptionIds.length===0 && backend.filters.serverIds.length===0,"Directory switch kept old scopes/resources"))return;
        backend.switchAccount(1);test.stage=17;
      } else if(test.stage===17 && backend.databaseRows.length) {
        if(!test.check(backend.profileId==="44444444-4444-4444-8444-444444444444" && backend.accountRows[1].username==="second@example.test","Account switch did not use isolated profile"))return;
        // Queue a live operation, then immediately change identities; the old reply must be discarded.
        backend.refreshLive();backend.switchAccount(0);test.stage=18;
      } else if(test.stage===18 && backend.databaseRows.length) {
        if(!test.check(backend.profileId==="cli" && backend.tenantId==="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","Account-specific directory choice was not remembered"))return;
        backend.panelClosed();backend.panelOpened();test.stage=19;
      } else if(test.stage===19 && backend.databaseRows.length) {
        if(!test.check(backend.profileId==="cli" && backend.tenantId==="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","Reopen lost account/directory selection"))return;
        backend.panelClosed();
        if(!test.check(!test.named("identityControls").visible,"Identity controls must collapse when panel closes"))return;
        test.named("identityToggleButton").clicked();
        test.named("addAzureDirectoryButton").clicked();test.stage=20;
      } else if(test.stage===20) {
        if(!test.check(!test.named("startAccountLoginButton").enabled,"Invalid directory allowed login"))return;
        test.named("loginTenantField").text="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";test.stage=21;
      } else if(test.stage===21) {
        if(!test.check(test.named("startAccountLoginButton").enabled,"Valid directory blocked login"))return;
        test.named("accountLoginDialog").close();
        console.log("QML_CHECK_PASSED");Qt.quit();
      }
    }
  }
}
