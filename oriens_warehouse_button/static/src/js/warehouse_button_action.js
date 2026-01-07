// odoo.define('oriens_warehouse_button.warehouse_button_action', function(require) {
//     "use strict";

//     var rpc = require('web.rpc');
//     var Dialog = require('web.Dialog');
//     var ActionManager = require('web.ActionManager');

//     window.openWarehouseAction = function(line_id) {
//         rpc.query({
//             model: 'sale.order.line',
//             method: 'warehouse_button_action',
//             args: [
//                 [line_id]
//             ],
//         }).then(function(action) {
//             if (action) {
//                 var action_manager = require('web.current_session').get_action_manager();
//                 action_manager.do_action(action);
//             } else {
//                 Dialog.alert(null, "Could not find the action for this product.");
//             }
//         }).fail(function(error) {
//             console.error('RPC query failed:', error);
//         });
//     };
// });